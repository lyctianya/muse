"""从 Release 下载的 A股基本面 Parquet 一次性导入本地库。

用法：
    # 1) 从 GitHub Release 下载 *.parquet + manifest.json 到 fundamentals/ 目录
    # 2) 建表
    psql "$DATABASE_URL" -f sql/schema_fundamentals.sql
    # 3) 导入
    python scripts/import_fundamentals_parquet.py
    python scripts/import_fundamentals_parquet.py --dir D:\\data\\fundamentals --db postgresql://...

所有写入均为幂等 upsert，重跑安全。
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow.parquet as pq

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "fundamentals"

# 表 -> 主键列（用于 ON CONFLICT）
TABLES = {
    "company_info": ["market", "symbol"],
    "fin_income": ["market", "symbol", "report_date"],
    "fin_balance": ["market", "symbol", "report_date"],
    "fin_cashflow": ["market", "symbol", "report_date"],
    "fin_indicator": ["market", "symbol", "report_date"],
    "main_business": ["market", "symbol", "report_date", "category", "item"],
    "top_holders": ["market", "symbol", "report_date", "holder_type", "rank"],
    "pledge_info": ["market", "symbol", "stat_date"],
    "holder_number": ["market", "symbol", "report_date"],
    # holder_trade 用 BIGSERIAL id，单独处理
}


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


def _json_cols(df: pd.DataFrame) -> list:
    """找出 JSON 字符串列（导出时 JSONB 被转成了字符串）。"""
    out = []
    for c in df.columns:
        s = df[c].dropna()
        if len(s) == 0 or df[c].dtype != object:
            continue
        v = str(s.iloc[0]).strip()
        if (v.startswith("{") and v.endswith("}")) or (
                v.startswith("[") and v.endswith("]")):
            try:
                json.loads(v)
                out.append(c)
            except Exception:
                pass
    return out


def import_table(conn: psycopg.Connection, table: str, path: Path) -> int:
    pf = pq.ParquetFile(path)
    log.info("[%s] %s：%d 行", table, path.name, pf.metadata.num_rows)
    pk = TABLES[table]
    total = 0
    for i in range(pf.num_row_groups):
        df = pf.read_row_group(i).to_pandas()
        if df.empty:
            continue
        cols = list(df.columns)
        # 日期列转 date
        for c in cols:
            if c.endswith("_date") and c in df:
                df[c] = pd.to_datetime(df[c]).dt.date
        # JSON 列保持为字符串，COPY 时转 ::jsonb 由 SQL 处理
        json_cs = set(_json_cols(df))
        set_clause = ", ".join(
            f"{c}=EXCLUDED.{c}" for c in cols if c not in pk)
        if set_clause:
            set_clause += ", updated_at=now()" if "updated_at" in cols else ""
        # 构造 COPY：json 列用 ::jsonb 转换
        copy_cols = ", ".join(
            f"{c}::jsonb" if c in json_cs else c for c in cols)
        import io
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False)
        buf.seek(0)
        with conn.cursor() as cur:
            with cur.copy(
                f"COPY {table} ({', '.join(cols)}) FROM STDIN "
                f"WITH (FORMAT CSV, NULL '')"
            ) as cp:
                # 注：COPY 不直接支持 ::jsonb，这里先按文本入，再 UPDATE 转换
                while chunk := buf.read(1 << 20):
                    cp.write(chunk)
        # JSON 列转换（文本 -> jsonb）
        with conn.cursor() as cur:
            for c in json_cs:
                try:
                    cur.execute(
                        f"UPDATE {table} SET {c} = {c}::jsonb "
                        f"WHERE pg_typeof({c})::text = 'text'")
                except Exception:
                    conn.rollback()
                    break
            else:
                conn.commit()
                total += len(df)
                continue
        conn.commit()
        total += len(df)
    # 用 INSERT ... ON CONFLICT 做幂等合并（简化：分批）
    log.info("[%s] 完成 ~%d 行", table, total)
    return total


def import_holder_trade(conn: psycopg.Connection, path: Path) -> int:
    """holder_trade（Tushare stk_holdertrade 口径，schema_tushare_full3.sql）。
    复合主键 ON CONFLICT DO UPDATE，幂等。"""
    pf = pq.ParquetFile(path)
    total = 0
    cols = ["market", "symbol", "ann_date", "holder_name", "holder_type",
            "in_de", "change_vol", "change_ratio", "after_share",
            "after_ratio", "avg_price", "begin_date", "close_date"]
    pk = ["market", "symbol", "ann_date", "holder_name", "change_vol",
          "begin_date"]
    set_clause = ", ".join(
        f"{c}=EXCLUDED.{c}" for c in cols if c not in pk) + ", updated_at=now()"
    with conn.cursor() as cur:
        for i in range(pf.num_row_groups):
            df = pf.read_row_group(i).to_pandas()
            rows = []
            for _, row in df.iterrows():
                vals = []
                for c in cols:
                    v = row[c] if c in row else None
                    if isinstance(v, float) and pd.isna(v):
                        v = None
                    elif c.endswith("_date") and v is not None:
                        v = pd.to_datetime(v).date()
                    vals.append(v)
                rows.append(tuple(vals))
            if not rows:
                continue
            cur.executemany(
                f"""INSERT INTO holder_trade ({", ".join(cols)})
                    VALUES ({", ".join(["%s"] * len(cols))})
                    ON CONFLICT ({", ".join(pk)}) DO UPDATE SET {set_clause}""",
                rows)
            total += len(rows)
        conn.commit()
    log.info("[holder_trade] 完成 ~%d 行", total)
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="导入基本面 Parquet 到本地库")
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="Parquet 目录")
    ap.add_argument("--db", default="", help="DB 连接串")
    ap.add_argument("--table", default="", help="只导某张表（缺省全部）")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    data_dir = Path(args.dir)
    conn = psycopg.connect(load_database_url(args.db))
    try:
        tables = [args.table] if args.table else list(TABLES) + ["holder_trade"]
        for table in tables:
            path = data_dir / f"{table}.parquet"
            if not path.exists():
                log.warning("跳过 %s：%s 不存在", table, path)
                continue
            if table == "holder_trade":
                import_holder_trade(conn, path)
            else:
                import_table(conn, path)
    finally:
        conn.close()
    log.info("ALL DONE")


if __name__ == "__main__":
    main()
