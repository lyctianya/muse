"""Tushare 41 张表 Parquet 幂等导入本地库。

用法：
    # 1) 从 GitHub Release 下载 *.parquet（+ manifest.json，可选）到目录
    # 2) 建表（目标库需先有表结构；可用 Release 中的 schema.sql）
    psql "$DATABASE_URL" -f schema.sql
    # 3) 导入
    python scripts/import_tushare_parquet.py --dir ./tushare-data
    python scripts/import_tushare_parquet.py --dir D:\\data\\tushare --db postgresql://...

原理：每张表建 TEMP 表 -> CSV COPY 高速写入 -> INSERT ... ON CONFLICT 幂等合并。
重跑安全；JSONB 列由 COPY 直接解析（导出时已转成合法 JSON 字符串）。
"""
import argparse
import io
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
DEFAULT_DIR = ROOT / "tushare-data"

# 与 scripts/export_tushare.py、merger/merger.py 中的注册表保持一致
TABLES = [
    {"name": "company_info", "pk": ["market", "symbol"]},
    {"name": "fin_income", "pk": ["market", "symbol", "report_date"]},
    {"name": "fin_balance", "pk": ["market", "symbol", "report_date"]},
    {"name": "fin_cashflow", "pk": ["market", "symbol", "report_date"]},
    {"name": "fin_indicator", "pk": ["market", "symbol", "report_date"]},
    {"name": "top_holders", "pk": ["market", "symbol", "report_date", "holder_type", "rank"]},
    {"name": "holder_number", "pk": ["market", "symbol", "report_date"]},
    {"name": "pledge_info", "pk": ["market", "symbol", "stat_date"]},
    {"name": "daily_basic", "pk": ["market", "symbol", "trade_date"]},
    {"name": "dividend", "pk": ["market", "symbol", "ann_date", "end_date"]},
    {"name": "forecast", "pk": ["market", "symbol", "ann_date", "end_date"]},
    {"name": "express", "pk": ["market", "symbol", "end_date"]},
    {"name": "moneyflow", "pk": ["market", "symbol", "trade_date"]},
    {"name": "suspend", "pk": ["market", "symbol", "suspend_date"]},
    {"name": "fina_mainbz", "pk": ["market", "symbol", "end_date", "bz_item"]},
    {"name": "company_detail", "pk": ["market", "symbol"]},
    {"name": "namechange", "pk": ["market", "symbol", "start_date"]},
    {"name": "top_list", "pk": ["market", "symbol", "trade_date"]},
    {"name": "top_inst", "pk": ["market", "symbol", "trade_date", "side", "exalter"]},
    {"name": "index_daily", "pk": ["market", "ts_code", "trade_date"]},
    {"name": "moneyflow_hsgt", "pk": ["market", "trade_date"]},
    {"name": "hsgt_top10", "pk": ["market", "symbol", "trade_date", "gtype"]},
    {"name": "disclosure_date", "pk": ["market", "symbol", "end_date"]},
    {"name": "margin", "pk": ["market", "trade_date", "exchange_id"]},
    {"name": "margin_detail", "pk": ["market", "symbol", "trade_date"]},
    {"name": "stk_limit", "pk": ["market", "symbol", "trade_date"]},
    {"name": "fina_audit", "pk": ["market", "symbol", "end_date"]},
    {"name": "new_share", "pk": ["market", "symbol"]},
    {"name": "managers", "pk": ["market", "symbol", "name", "ann_date"]},
    {"name": "share_float", "pk": ["market", "symbol", "float_date", "holder_name"]},
    {"name": "block_trade", "pk": ["market", "symbol", "trade_date", "price", "vol"]},
    {"name": "adj_factor", "pk": ["market", "symbol", "trade_date"]},
    {"name": "holder_trade", "pk": ["market", "symbol", "ann_date", "holder_name", "change_vol", "begin_date"]},
    {"name": "daily_ts", "pk": ["market", "symbol", "trade_date"]},
    {"name": "repurchase", "pk": ["market", "symbol", "ann_date"]},
    {"name": "pledge_detail", "pk": ["market", "symbol", "ann_date", "holder_name", "start_date"]},
    {"name": "index_basic", "pk": ["ts_code"]},
    {"name": "index_weight", "pk": ["index_code", "con_code", "trade_date"]},
    {"name": "index_member", "pk": ["index_code", "con_code"]},
    {"name": "cyq_perf", "pk": ["market", "symbol", "trade_date"]},
    {"name": "hk_hold", "pk": ["market", "symbol", "trade_date"]},
]


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


def _db_columns(conn, table: str) -> list:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name=%s
               ORDER BY ordinal_position""",
            (table,))
        return [r[0] for r in cur.fetchall()]


def import_table(conn, table: str, pk: list, path: Path) -> int:
    db_cols = _db_columns(conn, table)
    if not db_cols:
        log.warning("[%s] 目标库无此表，跳过（先执行 schema.sql 建表）", table)
        return 0
    pf = pq.ParquetFile(path)
    log.info("[%s] %s：%d 行", table, path.name, pf.metadata.num_rows)
    # parquet 列与库表列取交集（防 schema 漂移）
    pq_cols = pf.schema.names
    cols = [c for c in pq_cols if c in db_cols]
    if not cols:
        log.warning("[%s] 无共同列，跳过", table)
        return 0
    pk = [c for c in pk if c in cols]
    set_cols = [c for c in cols if c not in pk]
    set_clause = ", ".join(f'"{c}"=EXCLUDED."{c}"' for c in set_cols)
    if "updated_at" in set_cols:
        pass  # 已包含在 set_cols 中
    elif "updated_at" in db_cols:
        set_clause += (", " if set_clause else "") + "updated_at=now()"

    col_list = ", ".join(f'"{c}"' for c in cols)
    total = 0
    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS _imp; CREATE TEMP TABLE _imp (LIKE "{table}")')
        try:
            for i in range(pf.num_row_groups):
                df = pf.read_row_group(i).to_pandas()[cols]
                # 日期/时间列统一转字符串，COPY 可解析；NaN -> 空 -> NULL
                for c in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[c]):
                        df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S%z")
                    elif str(df[c].dtype) == "date":
                        df[c] = df[c].astype(str)
                buf = io.StringIO()
                df.to_csv(buf, index=False, header=False)
                buf.seek(0)
                with cur.copy(
                    f'COPY _imp ({col_list}) FROM STDIN WITH (FORMAT CSV, NULL \'\')'
                ) as cp:
                    while chunk := buf.read(1 << 20):
                        cp.write(chunk)
                total += len(df)
            if set_clause:
                cur.execute(
                    f'INSERT INTO "{table}" ({col_list}) SELECT {col_list} FROM _imp '
                    f'ON CONFLICT ({", ".join(pk)}) DO UPDATE SET {set_clause}')
            else:
                cur.execute(
                    f'INSERT INTO "{table}" ({col_list}) SELECT {col_list} FROM _imp '
                    f'ON CONFLICT ({", ".join(pk)}) DO NOTHING')
        finally:
            cur.execute("DROP TABLE IF EXISTS _imp")
    conn.commit()
    log.info("[%s] 合并完成：%d 行", table, total)
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Tushare Parquet 幂等导入本地库")
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="Parquet 目录")
    ap.add_argument("--db", default="", help="DB 连接串")
    ap.add_argument("--table", default="", help="只导某张表（缺省全部）")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    data_dir = Path(args.dir)
    conn = psycopg.connect(load_database_url(args.db))
    try:
        specs = [t for t in TABLES if not args.table or t["name"] == args.table]
        if args.table and not specs:
            raise SystemExit(f"未知表：{args.table}")
        for spec in specs:
            path = data_dir / f"{spec['name']}.parquet"
            if not path.exists():
                log.warning("跳过 %s：%s 不存在", spec["name"], path)
                continue
            try:
                import_table(conn, spec["name"], spec["pk"], path)
            except Exception as exc:
                conn.rollback()
                log.error("[%s] 导入失败：%s", spec["name"], exc)
    finally:
        conn.close()
    log.info("ALL DONE")


if __name__ == "__main__":
    main()
