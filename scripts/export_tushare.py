"""Tushare 41 张表导出 + GitHub Release 发布。

用法（在本机跑）：
    # 先回填（见 docs/USAGE.md）
    .\\.venv\\Scripts\\python scripts/export_tushare.py --tag tushare-2026-09-29

特性：
- 41 张 Tushare 表各导出一个 Parquet（含 manifest.json + schema.sql）
- 数据保留策略：日线类（daily_basic/daily_ts/adj_factor/index_daily）近 10 年，
  其余带日期列的表近 2 年，维度表（company_detail/index_basic/index_member/new_share/company_info）全量
- JSONB 列转 JSON 字符串，Parquet 兼容
- 用 gh CLI 发布到 GitHub Release（需先 gh auth login）；同名 Release 已存在则跳过
- 幂等：重复导出同 tag 会覆盖本地文件，Release 已存在则不重复创建
"""
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
REPO = os.environ.get("GITHUB_REPO", "lyctianya/muse")

# 表注册：name / 主键 / 日期列（用于保留期裁剪）/ 保留年数（None=全量）
# 与 scripts/import_tushare_parquet.py、merger/merger.py 中的注册表保持一致
TABLES = [
    # 基本面 8 张
    {"name": "company_info", "pk": ["market", "symbol"], "date_col": None, "years": None},
    {"name": "fin_income", "pk": ["market", "symbol", "report_date"], "date_col": "report_date", "years": 2},
    {"name": "fin_balance", "pk": ["market", "symbol", "report_date"], "date_col": "report_date", "years": 2},
    {"name": "fin_cashflow", "pk": ["market", "symbol", "report_date"], "date_col": "report_date", "years": 2},
    {"name": "fin_indicator", "pk": ["market", "symbol", "report_date"], "date_col": "report_date", "years": 2},
    {"name": "top_holders", "pk": ["market", "symbol", "report_date", "holder_type", "rank"], "date_col": "report_date", "years": 2},
    {"name": "holder_number", "pk": ["market", "symbol", "report_date"], "date_col": "report_date", "years": 2},
    {"name": "pledge_info", "pk": ["market", "symbol", "stat_date"], "date_col": "stat_date", "years": 2},
    # 增量 6 张
    {"name": "daily_basic", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 10},
    {"name": "dividend", "pk": ["market", "symbol", "ann_date", "end_date"], "date_col": "ann_date", "years": 2},
    {"name": "forecast", "pk": ["market", "symbol", "ann_date", "end_date"], "date_col": "ann_date", "years": 2},
    {"name": "express", "pk": ["market", "symbol", "end_date"], "date_col": "end_date", "years": 2},
    {"name": "moneyflow", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "suspend", "pk": ["market", "symbol", "suspend_date"], "date_col": "suspend_date", "years": 2},
    # 全量 15 张
    {"name": "fina_mainbz", "pk": ["market", "symbol", "end_date", "bz_item"], "date_col": "end_date", "years": 2},
    {"name": "company_detail", "pk": ["market", "symbol"], "date_col": None, "years": None},
    {"name": "namechange", "pk": ["market", "symbol", "start_date"], "date_col": "start_date", "years": 2},
    {"name": "top_list", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "top_inst", "pk": ["market", "symbol", "trade_date", "side", "exalter"], "date_col": "trade_date", "years": 2},
    {"name": "index_daily", "pk": ["market", "ts_code", "trade_date"], "date_col": "trade_date", "years": 10},
    {"name": "moneyflow_hsgt", "pk": ["market", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "hsgt_top10", "pk": ["market", "symbol", "trade_date", "gtype"], "date_col": "trade_date", "years": 2},
    {"name": "disclosure_date", "pk": ["market", "symbol", "end_date"], "date_col": "end_date", "years": 2},
    {"name": "margin", "pk": ["market", "trade_date", "exchange_id"], "date_col": "trade_date", "years": 2},
    {"name": "margin_detail", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "stk_limit", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "fina_audit", "pk": ["market", "symbol", "end_date"], "date_col": "end_date", "years": 2},
    {"name": "new_share", "pk": ["market", "symbol"], "date_col": None, "years": None},
    {"name": "managers", "pk": ["market", "symbol", "name", "ann_date"], "date_col": "ann_date", "years": 2},
    # 全量2 2 张
    {"name": "share_float", "pk": ["market", "symbol", "float_date", "holder_name"], "date_col": "float_date", "years": 2},
    {"name": "block_trade", "pk": ["market", "symbol", "trade_date", "price", "vol"], "date_col": "trade_date", "years": 2},
    # 全量3 10 张
    {"name": "adj_factor", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 10},
    {"name": "holder_trade", "pk": ["market", "symbol", "ann_date", "holder_name", "change_vol", "begin_date"], "date_col": "ann_date", "years": 2},
    {"name": "daily_ts", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 10},
    {"name": "repurchase", "pk": ["market", "symbol", "ann_date"], "date_col": "ann_date", "years": 2},
    {"name": "pledge_detail", "pk": ["market", "symbol", "ann_date", "holder_name", "start_date"], "date_col": "ann_date", "years": 2},
    {"name": "index_basic", "pk": ["ts_code"], "date_col": None, "years": None},
    {"name": "index_weight", "pk": ["index_code", "con_code", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "index_member", "pk": ["index_code", "con_code"], "date_col": None, "years": None},
    {"name": "cyq_perf", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 2},
    {"name": "hk_hold", "pk": ["market", "symbol", "trade_date"], "date_col": "trade_date", "years": 2},
]

SCHEMA_FILES = [
    "sql/schema_fundamentals.sql",
    "sql/schema_tushare_extra.sql",
    "sql/schema_tushare_full.sql",
    "sql/schema_tushare_full2.sql",
    "sql/schema_tushare_full3.sql",
]


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("设置 DATABASE_URL 或项目 .env")


def _cutoff(years: int) -> date:
    t = date.today()
    try:
        return t.replace(year=t.year - years)
    except ValueError:
        return t.replace(year=t.year - years, day=28)


def export_tables(db_url: str, out_dir: Path, only: str = "") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "tag": "",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "market": "cn",
        "scope": "Tushare 41 张表（日线类近10年，其余近2年）",
        "retention": "daily_basic/daily_ts/adj_factor/index_daily: 10y; others: 2y; dimensions: full",
        "tables": {},
    }
    conn = psycopg.connect(db_url)
    try:
        for spec in TABLES:
            table = spec["name"]
            if only and table != only:
                continue
            where, params = "", []
            if spec["date_col"] and spec["years"]:
                where = f"WHERE {spec['date_col']} >= %s"
                params = [_cutoff(spec["years"])]
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM information_schema.tables
                       WHERE table_schema='public' AND table_name=%s""",
                    (table,))
                if not cur.fetchone():
                    log.warning("%s 在库中不存在，跳过", table)
                    manifest["tables"][table] = {"rows": 0, "file": None}
                    continue
                cur.execute(f"SELECT COUNT(*) FROM {table} {where}", params)
                n = cur.fetchone()[0]
            path = out_dir / f"{table}.parquet"
            if n == 0:
                log.warning("%s 为空，跳过", table)
                manifest["tables"][table] = {"rows": 0, "file": None}
                continue
            chunks = []
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {table} {where}", params)
                cols = [d[0] for d in cur.description]
                while True:
                    rows = cur.fetchmany(50000)
                    if not rows:
                        break
                    chunks.append(pd.DataFrame(rows, columns=cols))
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].apply(
                        lambda v: json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (dict, list)) else v)
            df.to_parquet(path, index=False)
            size = path.stat().st_size
            # 日期范围（用于 manifest）
            date_from = date_to = None
            if spec["date_col"] and spec["date_col"] in df.columns:
                s = pd.to_datetime(df[spec["date_col"]], errors="coerce").dropna()
                if len(s):
                    date_from, date_to = s.min().date().isoformat(), s.max().date().isoformat()
            log.info("%s: %d 行 -> %s (%.1f MB)", table, n, path.name, size / 1e6)
            manifest["tables"][table] = {
                "rows": n, "file": path.name, "size": size,
                "date_from": date_from, "date_to": date_to,
            }
    finally:
        conn.close()
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def export_schema(db_url: str, out_dir: Path) -> None:
    """导出 41 张表的建表语句，供 merger --fundamentals 自建表。"""
    dest = out_dir / "schema.sql"
    tables = [t["name"] for t in TABLES]
    pg_dump = shutil.which("pg_dump")
    if pg_dump:
        cmd = [pg_dump, db_url, "--schema-only", "--no-owner", "--no-privileges"]
        for t in tables:
            cmd += ["-t", t]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and "CREATE TABLE" in r.stdout:
            dest.write_text(r.stdout, encoding="utf-8")
            log.info("schema.sql 已生成（pg_dump，共 %d 张表）", len(tables))
            return
        log.warning("pg_dump 失败，回退到拼接 sql/ 文件")
    # 回退：拼接项目内 schema 文件（去掉 full3 的 DROP，避免误伤）
    parts = []
    for rel in SCHEMA_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        txt = "\n".join(
            ln for ln in txt.splitlines()
            if not ln.strip().upper().startswith("DROP TABLE"))
        parts.append(f"-- ===== {rel} =====\n" + txt)
    dest.write_text("\n\n".join(parts), encoding="utf-8")
    log.info("schema.sql 已生成（拼接 sql/ 文件）")


def gh_release(tag: str, out_dir: Path, manifest: dict) -> None:
    manifest["tag"] = tag
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    r = subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO],
        capture_output=True, text=True)
    if r.returncode == 0:
        log.info("Release %s 已存在，跳过创建", tag)
        return
    files = [str(p) for p in sorted(out_dir.glob("*.parquet"))]
    files += [str(out_dir / "manifest.json"), str(out_dir / "schema.sql")]
    total = sum(t["rows"] for t in manifest["tables"].values())
    title = f"A股 Tushare 数据（41 张表）{date.today().isoformat()}"
    notes = (
        f"A股 Tushare 数据导出（{date.today().isoformat()}）\n\n"
        f"共 {len(manifest['tables'])} 张表，{total} 行。\n"
        f"保留策略：日线类近 10 年，其余近 2 年，维度表全量。\n\n"
        "导入：python scripts/import_tushare_parquet.py --dir <解压目录>\n"
        "或用 merger：python merger/merger.py --repo OWNER/REPO --db <连接串> --fundamentals\n")
    subprocess.run(
        ["gh", "release", "create", tag, *files,
         "--repo", REPO, "--title", title, "--notes", notes],
        check=True)
    log.info("Release %s 已发布", tag)


def main() -> None:
    ap = argparse.ArgumentParser(description="Tushare 41 张表导出 + Release")
    ap.add_argument("--tag", required=True, help="Release tag，如 tushare-2026-09-29")
    ap.add_argument("--out", default="", help="导出目录（缺省为临时目录）")
    ap.add_argument("--no-release", action="store_true", help="只导出不发布")
    ap.add_argument("--table", default="", help="只导出某张表（调试用）")
    ap.add_argument("--no-schema", action="store_true", help="不导出 schema.sql")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")

    out_dir = Path(args.out) if args.out else Path(
        tempfile.mkdtemp(prefix="tushare-"))
    db_url = load_database_url()
    manifest = export_tables(db_url, out_dir, only=args.table)
    if not args.no_schema and not args.table:
        export_schema(db_url, out_dir)
    total = sum(t["rows"] for t in manifest["tables"].values())
    log.info("导出完成：%d 张表，共 %d 行 -> %s",
             len(manifest["tables"]), total, out_dir)
    if not args.no_release:
        gh_release(args.tag, out_dir, manifest)
    print(f"OUT_DIR={out_dir}")


if __name__ == "__main__":
    main()
