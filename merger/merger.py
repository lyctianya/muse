"""合并工具（用户侧独立运行）：从 GitHub Releases 下载 Parquet，
幂等合并到本地 PostgreSQL。

用法：
    pip install -r merger/requirements.txt
    python merger/merger.py --repo owner/repo --db postgresql://user:pass@host:5432/stocks
    # 同时合并基本面（tushare-YYYY-MM-DD / fundamentals-YYYY-MM-DD）
    python merger/merger.py --repo owner/repo --db <连接串> --fundamentals

流程：
1. 调 GitHub API 列出 Releases，按 tag=data-YYYY-Www 解析周次
2. 查本地 ingested_weeks 表，跳过已入库的周
3. 下载缺失周的 parquet（每市场一个文件）-> pyarrow 读取 -> COPY 极速入库
4. 登记 ingested_weeks；全程幂等，可反复重跑
5. --fundamentals：再处理基本面 Release，先执行自带的 schema.sql 建表，
   再逐表 TEMP+COPY+ON CONFLICT 合并，登记 ingested_fundamentals
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
# 基本面 Release tag：tushare-YYYY-MM-DD（新）/ fundamentals-YYYY-MM-DD（旧）
TUSHARE_TAG_RE = re.compile(r"^tushare-(\d{4}-\d{2}-\d{2})$")
FUND_TAG_RE = re.compile(r"^fundamentals-(\d{4}-\d{2}-\d{2})$")

# Tushare 41 张表注册（name -> pk），与 scripts/export_tushare.py、
# scripts/import_tushare_parquet.py 保持一致
TUSHARE_TABLES = [
    ("company_info", ["market", "symbol"]),
    ("fin_income", ["market", "symbol", "report_date"]),
    ("fin_balance", ["market", "symbol", "report_date"]),
    ("fin_cashflow", ["market", "symbol", "report_date"]),
    ("fin_indicator", ["market", "symbol", "report_date"]),
    ("top_holders", ["market", "symbol", "report_date", "holder_type", "rank"]),
    ("holder_number", ["market", "symbol", "report_date"]),
    ("pledge_info", ["market", "symbol", "stat_date"]),
    ("daily_basic", ["market", "symbol", "trade_date"]),
    ("dividend", ["market", "symbol", "ann_date", "end_date"]),
    ("forecast", ["market", "symbol", "ann_date", "end_date"]),
    ("express", ["market", "symbol", "end_date"]),
    ("moneyflow", ["market", "symbol", "trade_date"]),
    ("suspend", ["market", "symbol", "suspend_date"]),
    ("fina_mainbz", ["market", "symbol", "end_date", "bz_item"]),
    ("company_detail", ["market", "symbol"]),
    ("namechange", ["market", "symbol", "start_date"]),
    ("top_list", ["market", "symbol", "trade_date"]),
    ("top_inst", ["market", "symbol", "trade_date", "side", "exalter"]),
    ("index_daily", ["market", "ts_code", "trade_date"]),
    ("moneyflow_hsgt", ["market", "trade_date"]),
    ("hsgt_top10", ["market", "symbol", "trade_date", "gtype"]),
    ("disclosure_date", ["market", "symbol", "end_date"]),
    ("margin", ["market", "trade_date", "exchange_id"]),
    ("margin_detail", ["market", "symbol", "trade_date"]),
    ("stk_limit", ["market", "symbol", "trade_date"]),
    ("fina_audit", ["market", "symbol", "end_date"]),
    ("new_share", ["market", "symbol"]),
    ("managers", ["market", "symbol", "name", "ann_date"]),
    ("share_float", ["market", "symbol", "float_date", "holder_name"]),
    ("block_trade", ["market", "symbol", "trade_date", "price", "vol"]),
    ("adj_factor", ["market", "symbol", "trade_date"]),
    ("holder_trade", ["market", "symbol", "ann_date", "holder_name", "change_vol", "begin_date"]),
    ("daily_ts", ["market", "symbol", "trade_date"]),
    ("repurchase", ["market", "symbol", "ann_date", "proc"]),
    ("pledge_detail", ["market", "symbol", "ann_date", "holder_name", "start_date"]),
    ("index_basic", ["ts_code"]),
    ("index_weight", ["index_code", "con_code", "trade_date"]),
    ("index_member", ["index_code", "con_code"]),
    ("cyq_perf", ["market", "symbol", "trade_date"]),
    ("hk_hold", ["market", "symbol", "trade_date"]),
]
# 旧版 fundamentals-* Release 的 10 张表（东财时代口径，仅兼容）
LEGACY_TABLES = [
    ("company_info", ["market", "symbol"]),
    ("fin_income", ["market", "symbol", "report_date"]),
    ("fin_balance", ["market", "symbol", "report_date"]),
    ("fin_cashflow", ["market", "symbol", "report_date"]),
    ("fin_indicator", ["market", "symbol", "report_date"]),
    ("main_business", ["market", "symbol", "report_date", "category", "item"]),
    ("top_holders", ["market", "symbol", "report_date", "holder_type", "rank"]),
    ("pledge_info", ["market", "symbol", "stat_date"]),
    ("holder_number", ["market", "symbol", "report_date"]),
    # holder_trade 旧口径已废弃（表结构已迁移），旧包中的该文件跳过
]
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
CREATE TABLE IF NOT EXISTS ingested_fundamentals (
    tag TEXT PRIMARY KEY,            -- 已合并的基本面 Release tag
    merged_at TIMESTAMPTZ NOT NULL DEFAULT now()
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


def parse_fund_tag(tag: str):
    """解析基本面 Release tag，返回 (kind, date_str)。"""
    m = TUSHARE_TAG_RE.match(tag or "")
    if m:
        return ("tushare", m.group(1))
    m = FUND_TAG_RE.match(tag or "")
    if m:
        return ("fundamentals", m.group(1))
    return (None, None)


def get_ingested_fundamentals(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT tag FROM ingested_fundamentals")
        return {r[0] for r in cur.fetchall()}


def apply_schema_sql(conn, path: Path) -> None:
    """执行 Release 自带的 schema.sql（建表，IF NOT EXISTS 安全）。"""
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    log.info("schema.sql 已执行")


def merge_fund_table(conn, parquet_path: Path, table: str, pk: list) -> int:
    """单张基本面表：TEMP 表 + COPY + ON CONFLICT 幂等合并。"""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name=%s
               ORDER BY ordinal_position""",
            (table,))
        db_cols = [r[0] for r in cur.fetchall()]
    if not db_cols:
        log.warning("[%s] 目标库无此表，跳过（Release 中 schema.sql 可建表）", table)
        return 0
    pf = pq.ParquetFile(parquet_path)
    cols = [c for c in pf.schema.names if c in db_cols]
    if not cols:
        log.warning("[%s] 无共同列，跳过", table)
        return 0
    pk = [c for c in pk if c in cols]
    set_cols = [c for c in cols if c not in pk]
    set_clause = ", ".join(f'"{c}"=EXCLUDED."{c}"' for c in set_cols)
    if "updated_at" in db_cols and "updated_at" not in set_cols:
        set_clause += (", " if set_clause else "") + "updated_at=now()"
    col_list = ", ".join(f'"{c}"' for c in cols)
    total = 0
    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS _imp; CREATE TEMP TABLE _imp (LIKE "{table}")')
        try:
            for i in range(pf.num_row_groups):
                df = pf.read_row_group(i).to_pandas()[cols]
                for c in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[c]):
                        df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S%z")
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
    return total


def merge_fundamentals_release(conn, tag: str, kind: str, release: dict,
                               data_dir: Path) -> None:
    """合并一个基本面 Release：先建表（schema.sql），再逐表导入。"""
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    tables = TUSHARE_TABLES if kind == "tushare" else LEGACY_TABLES
    # 1) 建表
    if "schema.sql" in assets:
        dest = download_asset(assets["schema.sql"], data_dir / tag / "schema.sql")
        try:
            apply_schema_sql(conn, dest)
        except Exception as exc:
            log.warning("schema.sql 执行失败（%s），假设表已存在，继续", exc)
            conn.rollback()
    # 2) 逐表
    for table, pk in tables:
        fname = f"{table}.parquet"
        if fname not in assets:
            log.warning("[%s] Release %s 中没有 %s，跳过", table, tag, fname)
            continue
        dest = download_asset(assets[fname], data_dir / tag / fname)
        try:
            n = merge_fund_table(conn, dest, table, pk)
            log.info("[%s <- %s] 合并完成：%d 行", table, tag, n)
        except Exception as exc:
            conn.rollback()
            log.error("[%s] 合并失败：%s", table, exc)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingested_fundamentals (tag) VALUES (%s)"
            " ON CONFLICT DO NOTHING",
            (tag,))
    conn.commit()
    log.info("Release %s 合并完成", tag)


def main() -> None:
    parser = argparse.ArgumentParser(description="周数据合并工具（GitHub Releases -> 本地 PG）")
    parser.add_argument("--repo", required=True, help="GitHub 仓库，形如 owner/repo")
    parser.add_argument("--db", default=os.environ.get("DATABASE_URL", ""),
                        help="目标库连接串，默认读 DATABASE_URL 环境变量")
    parser.add_argument("--data-dir", default="./merger-data", help="parquet 下载目录")
    parser.add_argument("--week", default=None, help="只合并指定周，如 2026-W39")
    parser.add_argument("--fundamentals", action="store_true",
                        help="同时合并基本面 Release（tushare-YYYY-MM-DD / fundamentals-YYYY-MM-DD）")
    parser.add_argument("--fund-tag", default=None,
                        help="只合并指定的基本面 Release tag，如 tushare-2026-09-29")
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
        # 基本面 Release
        if args.fundamentals or args.fund_tag:
            ingested_f = get_ingested_fundamentals(conn)
            fund_rels = []
            for rel in releases:
                tag = rel.get("tag_name", "")
                kind, _ = parse_fund_tag(tag)
                if not kind:
                    continue
                if args.fund_tag and tag != args.fund_tag:
                    continue
                if tag in ingested_f:
                    log.info("[%s] 已合并，跳过", tag)
                    continue
                fund_rels.append((tag, kind, rel))
            fund_rels.sort()
            if not fund_rels:
                log.info("没有可合并的基本面 Release")
            for tag, kind, rel in fund_rels:
                merge_fundamentals_release(conn, tag, kind, rel, data_dir)
        log.info("全部完成")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
