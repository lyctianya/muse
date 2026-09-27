"""A股基本面导出 + GitHub Release 发布（近 2 年）。

用法（在本机跑，沙箱网络不通）：
    # 1) 先回填
    .\\.venv\\Scripts\\python -m fetcher.jobs.backfill_fundamentals

    # 2) 导出 Parquet 并发布 Release
    .\\.venv\\Scripts\\python scripts/export_fundamentals.py --tag fundamentals-2026-09-27

特性：
- 10 张基本面表各导出一个 Parquet（含 manifest.json）
- 用 gh CLI 发布到 GitHub Release（需先 gh auth login）
- 幂等：同名 Release 已存在则跳过上传
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]

TABLES = [
    "company_info",
    "fin_income",
    "fin_balance",
    "fin_cashflow",
    "fin_indicator",
    "main_business",
    "top_holders",
    "pledge_info",
    "holder_number",
    "holder_trade",
]

REPO = os.environ.get("GITHUB_REPO", "lyctianya/muse")


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("设置 DATABASE_URL 或项目 .env")


def export_tables(db_url: str, out_dir: Path) -> dict:
    """每张表导出一个 Parquet，返回 manifest 数据。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "tag": "",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "market": "cn",
        "scope": "近2年基本面",
        "tables": {},
    }
    conn = psycopg.connect(db_url)
    try:
        for table in TABLES:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                n = cur.fetchone()[0]
            path = out_dir / f"{table}.parquet"
            if n == 0:
                log.warning("%s 为空，跳过", table)
                manifest["tables"][table] = {"rows": 0, "file": None}
                continue
            # 分批读，避免内存爆炸
            chunks = []
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {table}")
                cols = [d[0] for d in cur.description]
                while True:
                    rows = cur.fetchmany(50000)
                    if not rows:
                        break
                    chunks.append(pd.DataFrame(rows, columns=cols))
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            # JSONB 列转字符串，Parquet 兼容
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].apply(
                        lambda v: json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (dict, list)) else v)
            df.to_parquet(path, index=False)
            size = path.stat().st_size
            log.info("%s: %d 行 -> %s (%.1f MB)", table, n, path.name, size / 1e6)
            manifest["tables"][table] = {
                "rows": n, "file": path.name, "size": size}
    finally:
        conn.close()
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def gh_release(tag: str, out_dir: Path, manifest: dict) -> None:
    """用 gh CLI 创建 Release 并上传附件。"""
    manifest["tag"] = tag
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 检查 Release 是否已存在
    r = subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO],
        capture_output=True, text=True)
    if r.returncode == 0:
        log.info("Release %s 已存在，跳过创建", tag)
    else:
        files = [str(p) for p in sorted(out_dir.glob("*.parquet"))]
        files.append(str(out_dir / "manifest.json"))
        title = f"A股基本面数据（近2年）{date.today().isoformat()}"
        notes = (
            f"A股基本面数据，近 2 年（{date.today().isoformat()} 导出）\n\n"
            + "\n".join(f"- {t}: {manifest['tables'][t]['rows']} 行"
                        for t in TABLES))
        subprocess.run(
            ["gh", "release", "create", tag, *files,
             "--repo", REPO, "--title", title, "--notes", notes],
            check=True)
        log.info("Release %s 已发布", tag)


def main() -> None:
    ap = argparse.ArgumentParser(description="A股基本面导出 + Release")
    ap.add_argument("--tag", required=True, help="Release tag，如 fundamentals-2026-09-27")
    ap.add_argument("--out", default="", help="导出目录（缺省为临时目录）")
    ap.add_argument("--no-release", action="store_true", help="只导出不发布")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")

    out_dir = Path(args.out) if args.out else Path(
        tempfile.mkdtemp(prefix="fundamentals-"))
    manifest = export_tables(load_database_url(), out_dir)
    total = sum(t["rows"] for t in manifest["tables"].values())
    log.info("导出完成：共 %d 行 -> %s", total, out_dir)
    if not args.no_release:
        gh_release(args.tag, out_dir, manifest)
    print(f"OUT_DIR={out_dir}")


if __name__ == "__main__":
    main()
