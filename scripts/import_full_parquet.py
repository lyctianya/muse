"""One-shot import of sqldata full Parquet files into local PostgreSQL.

Usage:
    python scripts/import_full_parquet.py
    python scripts/import_full_parquet.py --dir release
    python scripts/import_full_parquet.py --db postgresql://stockapp:postgres@127.0.0.1:5432/stocks

Parquet files are read from <project>/sqldata by default (override with --dir):
    sqldata/cn-2016-2026-full.parquet
    sqldata/hk-2016-2026-full.parquet
    sqldata/us-2016-2026-full.parquet

Deps: psycopg[binary], pyarrow, pandas (same as merger)
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow.parquet as pq

# Avoid Windows console cp1252 UnicodeEncodeError on Chinese log text
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "sqldata"

COPY_COLS = [
    "market", "symbol", "trade_date", "open", "high", "low", "close",
    "volume", "amount", "pct_change", "currency",
]

FILES = {
    "cn": "cn-2016-2026-full.parquet",
    "hk": "hk-2016-2026-full.parquet",
    "us": "us-2016-2026-full.parquet",
}

STAGING_DDL = """
CREATE TEMP TABLE IF NOT EXISTS daily_bars_staging (
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    amount DOUBLE PRECISION,
    pct_change DOUBLE PRECISION,
    currency TEXT NOT NULL
)
"""

MERGE_SQL = f"""
INSERT INTO daily_bars ({', '.join(COPY_COLS)})
SELECT DISTINCT ON (market, symbol, trade_date)
       {', '.join(COPY_COLS)}
FROM daily_bars_staging
ORDER BY market, symbol, trade_date
ON CONFLICT (market, symbol, trade_date) DO UPDATE SET
    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
    close=EXCLUDED.close, volume=EXCLUDED.volume, amount=EXCLUDED.amount,
    pct_change=EXCLUDED.pct_change, currency=EXCLUDED.currency, updated_at=now()
"""


def load_database_url(cli_db: str) -> str:
    if cli_db:
        return cli_db
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url:
        return env_url
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("Pass --db, or set DATABASE_URL / project .env")


def copy_to_staging(conn: psycopg.Connection, df: pd.DataFrame) -> int:
    missing = [c for c in COPY_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    df = df[COPY_COLS].copy()
    # Schema requires non-null OHLC/volume; skip broken source rows
    before = len(df)
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    skipped = before - len(df)
    if skipped:
        log.warning("skipped %d rows with null OHLC/volume", skipped)
    df = df.drop_duplicates(
        subset=["market", "symbol", "trade_date"], keep="last"
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    with conn.cursor() as cur:
        with cur.copy(
            f"COPY daily_bars_staging ({', '.join(COPY_COLS)}) "
            "FROM STDIN WITH (FORMAT CSV, NULL '')"
        ) as cp:
            while chunk := buf.read(1 << 20):
                cp.write(chunk)
    return len(df)


def import_parquet(conn: psycopg.Connection, path: Path, market: str) -> int:
    pf = pq.ParquetFile(path)
    total = 0
    log.info("[%s] start %s (%d rows, %d row groups)",
             market, path.name, pf.metadata.num_rows, pf.num_row_groups)

    with conn.cursor() as cur:
        cur.execute(STAGING_DDL)
    conn.commit()

    # Merge per row group to bound temp size and handle cross-group dupes
    for i in range(pf.num_row_groups):
        df = pf.read_row_group(i).to_pandas()
        with conn.cursor() as cur:
            cur.execute("TRUNCATE daily_bars_staging")
        n = copy_to_staging(conn, df)
        with conn.cursor() as cur:
            cur.execute(MERGE_SQL)
            merged = cur.rowcount
        conn.commit()
        total += n if merged < 0 else merged
        log.info("[%s] group %d/%d merged ~%d (cumulative ~%d)",
                 market, i + 1, pf.num_row_groups, merged, total)

    log.info("[%s] merged into daily_bars: ~%d rows", market, total)
    return total


def fill_symbols(conn: psycopg.Connection) -> int:
    """从行情表补齐缺失的 symbols 行。

    名称暂时用代码占位（parquet 无名称）；之后需跑 daily_fetch / 基本面回填
    或从 company_info 回写真实名称。ON CONFLICT DO NOTHING，不覆盖已有名称。
    """
    sql = """
    INSERT INTO symbols (market, symbol, name, currency, active)
    SELECT DISTINCT market, symbol, symbol, currency, TRUE
    FROM daily_bars
    ON CONFLICT DO NOTHING
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        n = cur.rowcount
    conn.commit()
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Import sqldata full Parquet")
    parser.add_argument("--db", default="", help="DB connection URL")
    parser.add_argument("--market", choices=["cn", "hk", "us"], default=None,
                        help="Import only one market (default: all)")
    parser.add_argument("--dir", default=str(DEFAULT_DATA_DIR),
                        help="Directory holding the *-full.parquet files "
                             "(default: <project>/sqldata)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    db_url = load_database_url(args.db)
    data_dir = Path(args.dir)
    markets = [args.market] if args.market else list(FILES.keys())

    conn = psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("DROP INDEX IF EXISTS idx_bars_symbol_date")
            cur.execute("DROP INDEX IF EXISTS idx_bars_date")
        conn.commit()
        log.info("dropped secondary indexes for bulk load")

        for market in markets:
            path = data_dir / FILES[market]
            if not path.exists():
                raise SystemExit(f"file not found: {path}")
            n = import_parquet(conn, path, market)
            log.info("[%s] done: %d rows", market, n)

        with conn.cursor() as cur:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_bars_symbol_date "
                "ON daily_bars (market, symbol, trade_date DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_bars_date "
                "ON daily_bars (trade_date DESC)"
            )
        conn.commit()
        log.info("recreated secondary indexes")

        inserted = fill_symbols(conn)
        log.info("symbols placeholders inserted: %d", inserted)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT market, COUNT(*), COUNT(DISTINCT symbol), "
                "MIN(trade_date), MAX(trade_date) "
                "FROM daily_bars GROUP BY market ORDER BY market"
            )
            for row in cur.fetchall():
                log.info("verify daily_bars %s: rows=%s symbols=%s %s~%s", *row)
            cur.execute("SELECT COUNT(*) FROM symbols")
            log.info("verify symbols total: %s", cur.fetchone()[0])
    finally:
        conn.close()
    log.info("ALL DONE")


if __name__ == "__main__":
    main()
