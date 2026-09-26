"""合并工具（用户侧独立运行）：从 GitHub Releases 下载周 Parquet，
幂等合并到本地 PostgreSQL。

用法：
    pip install -r merger/requirements.txt
    python merger/merger.py --repo owner/repo --db postgresql://user:pass@host:5432/stocks

流程：
1. 调 GitHub API 列出 Releases，按 tag=data-YYYY-Www 解析周次
2. 查本地 ingested_weeks 表，跳过已入库的周
3. 下载缺失周的 parquet（每市场一个文件）-> pyarrow 读取 -> COPY 极速入库
4. 登记 ingested_weeks；全程幂等，可反复重跑
"""
import argparse
import io
import logging
import os
import re
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow.parquet as pq
import requests

log = logging.getLogger(__name__)

MARKETS = ["cn", "hk", "us"]
TAG_RE = re.compile(r"^data-(\d{4}-W\d{2})$")
COPY_COLS = [
    "market", "symbol", "trade_date", "open", "high", "low", "close",
    "volume", "amount", "pct_change", "currency",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS symbols (
    market TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT NOT NULL,
    currency TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (market, symbol)
);
CREATE TABLE IF NOT EXISTS daily_bars (
    market TEXT NOT NULL, symbol TEXT NOT NULL, trade_date DATE NOT NULL,
    open DOUBLE PRECISION NOT NULL, high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL, close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL, amount DOUBLE PRECISION,
    pct_change DOUBLE PRECISION, currency TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_bars_symbol_date
    ON daily_bars (market, symbol, trade_date DESC);
CREATE TABLE IF NOT EXISTS ingested_weeks (
    market TEXT NOT NULL, week TEXT NOT NULL,
    PRIMARY KEY (market, week)
);
"""


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()


def list_releases(repo: str) -> list:
    """列出仓库全部 Releases（含附件信息），自动翻页。"""
    releases, url = [], f"https://api.github.com/repos/{repo}/releases?per_page=100"
    while url:
        r = requests.get(url, timeout=30,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        releases += r.json()
        # 翻页：解析 Link 头
        url = None
        for part in r.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return releases


def parse_week_tag(tag: str):
    m = TAG_RE.match(tag or "")
    return m.group(1) if m else None


def get_ingested(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT market, week FROM ingested_weeks")
        return {(r[0], r[1]) for r in cur.fetchall()}


def download_asset(url: str, dest: Path) -> Path:
    if dest.exists():
        log.info("已存在，跳过下载：%s", dest.name)
        return dest
    log.info("下载 %s ...", dest.name)
    with requests.get(url, timeout=300, stream=True,
                       headers={"Accept": "application/octet-stream"}) as r:
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def copy_parquet_to_db(conn, parquet_path: Path, market: str, week: str) -> int:
    """读 parquet，经 COPY 写入 daily_bars，返回行数。"""
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    missing = [c for c in COPY_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{parquet_path.name} 缺列：{missing}")
    df = df[COPY_COLS].copy()
    # 日期统一为 YYYY-MM-DD 字符串；NaN -> 空（COPY 视为 NULL）
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    with conn.cursor() as cur:
        with cur.copy(
            f"COPY daily_bars ({', '.join(COPY_COLS)}) FROM STDIN WITH (FORMAT CSV, NULL '')"
        ) as cp:
            while chunk := buf.read(1 << 20):
                cp.write(chunk)
        # 幂等：COPY 可能产生重复主键冲突 -> 改用 upsert 兜底
        # （COPY 本身不支持 ON CONFLICT，因此先尝试 COPY，失败则逐批 upsert）
    conn.commit()
    return len(df)


def copy_parquet_upsert(conn, parquet_path: Path) -> int:
    """COPY 冲突时的兜底：分批 ON CONFLICT DO UPDATE。"""
    df = pq.read_table(parquet_path).to_pandas()
    df = df[COPY_COLS].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    sql = (
        f"INSERT INTO daily_bars ({', '.join(COPY_COLS)}) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (market, symbol, trade_date) DO UPDATE SET "
        "open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, "
        "close=EXCLUDED.close, volume=EXCLUDED.volume, amount=EXCLUDED.amount, "
        "pct_change=EXCLUDED.pct_change, currency=EXCLUDED.currency, updated_at=now()"
    )
    rows = [
        tuple(None if pd.isna(v) else v for v in rec)
        for rec in df.itertuples(index=False, name=None)
    ]
    with conn.cursor() as cur:
        for i in range(0, len(rows), 2000):
            cur.executemany(sql, rows[i:i + 2000])
    conn.commit()
    return len(rows)


def merge_week(conn, repo: str, week: str, release: dict, data_dir: Path) -> None:
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    ingested = get_ingested(conn)
    for market in MARKETS:
        if (market, week) in ingested:
            log.info("[%s %s] 已入库，跳过", market, week)
            continue
        fname = f"{market}-{week}.parquet"
        if fname not in assets:
            log.warning("[%s %s] Release 中没有 %s，跳过", market, week, fname)
            continue
        dest = download_asset(assets[fname], data_dir / fname)
        try:
            n = copy_parquet_to_db(conn, dest, market, week)
        except Exception as exc:
            log.warning("COPY 失败（%s），改用 upsert 兜底", exc)
            conn.rollback()
            n = copy_parquet_upsert(conn, dest)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingested_weeks (market, week) VALUES (%s, %s)"
                " ON CONFLICT DO NOTHING",
                (market, week),
            )
        conn.commit()
        log.info("[%s %s] 合并完成：%d 行", market, week, n)


def main() -> None:
    parser = argparse.ArgumentParser(description="周数据合并工具（GitHub Releases -> 本地 PG）")
    parser.add_argument("--repo", required=True, help="GitHub 仓库，形如 owner/repo")
    parser.add_argument("--db", default=os.environ.get("DATABASE_URL", ""),
                        help="目标库连接串，默认读 DATABASE_URL 环境变量")
    parser.add_argument("--data-dir", default="./merger-data", help="parquet 下载目录")
    parser.add_argument("--week", default=None, help="只合并指定周，如 2026-W39")
    args = parser.parse_args()

    if not args.db:
        raise SystemExit("请用 --db 指定目标库，或设置 DATABASE_URL 环境变量")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")

    data_dir = Path(args.data_dir)
    conn = psycopg.connect(args.db)
    try:
        ensure_schema(conn)
        releases = list_releases(args.repo)
        log.info("找到 %d 个 Releases", len(releases))
        weeks = []
        for rel in releases:
            week = parse_week_tag(rel.get("tag_name", ""))
            if week and (args.week is None or week == args.week):
                weeks.append((week, rel))
        weeks.sort()
        if not weeks:
            log.info("没有可合并的周数据")
            return
        for week, rel in weeks:
            merge_week(conn, args.repo, week, rel, data_dir)
        log.info("全部完成")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
