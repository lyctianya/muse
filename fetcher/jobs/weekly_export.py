"""每周导出任务：导出上周三市场日线为 Parquet + manifest.json，
并发布到 GitHub Release（公开仓库附件，不污染 git 历史）。

未配置 GITHUB_TOKEN / GITHUB_REPO 时只做本地导出并告警跳过发布。
"""
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from fetcher import config, db

log = logging.getLogger(__name__)

MARKETS = ["cn", "hk", "us"]
EXPORT_DIR = config.ROOT / "exports"
# Parquet 列与 daily_bars 对齐（去掉 updated_at）
PARQUET_COLUMNS = [
    "market", "symbol", "trade_date", "open", "high", "low", "close",
    "volume", "amount", "pct_change", "currency",
]


def last_week_range(today: date | None = None) -> tuple:
    """返回上一个自然周的 (周一, 周日, 周标签如 2026-W39)。

    以 Asia/Shanghai 日期为准；任务在每周一 06:10 运行，
    此时"上周"即刚结束的交易周。
    """
    today = today or datetime.now(ZoneInfo(config.TZ)).date()
    monday_this = today - timedelta(days=today.weekday())
    monday_last = monday_this - timedelta(days=7)
    sunday_last = monday_last + timedelta(days=6)
    iso_year, iso_week, _ = monday_last.isocalendar()
    return monday_last, sunday_last, f"{iso_year}-W{iso_week:02d}"


def export_market(market: str, start: date, end: date, out_dir: Path) -> tuple:
    """导出单个市场一周数据为 Parquet，返回 (文件路径, 行数)。"""
    with db.get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT market, symbol, trade_date, open, high, low, close,"
                " volume, amount, pct_change, currency"
                " FROM daily_bars"
                " WHERE market = %s AND trade_date BETWEEN %s AND %s"
                " ORDER BY symbol, trade_date",
                (market, start, end),
            )
            rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=PARQUET_COLUMNS)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 文件名中的周标签由调用方传入，这里用占位符替换
    path = out_dir / f"{market}-{start.isocalendar()[0]}-W{start.isocalendar()[1]:02d}.parquet"
    df.to_parquet(path, index=False)
    log.info("[%s] 导出 %d 行 -> %s", market, len(df), path.name)
    return path, len(df)


def build_manifest(week: str, start: date, end: date, files: dict) -> dict:
    return {
        "week": week,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "generated_at": datetime.now(ZoneInfo(config.TZ)).isoformat(),
        "files": files,  # {market: {"file": ..., "rows": ...}}
    }


# ---------------- GitHub Release 发布 ----------------

_API = "https://api.github.com"


def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def publish_release(week: str, manifest: dict, parquet_paths: list) -> None:
    """创建（或复用）tag=data-{week} 的 Release 并上传附件。"""
    repo = config.GITHUB_REPO
    tag = f"data-{week}"
    session = requests.Session()
    session.headers.update(_gh_headers())

    # 1. 按 tag 查 Release，不存在则创建
    r = session.get(f"{_API}/repos/{repo}/releases/tags/{tag}", timeout=30)
    if r.status_code == 200:
        release = r.json()
        log.info("Release %s 已存在，复用", tag)
    else:
        r = session.post(
            f"{_API}/repos/{repo}/releases",
            json={
                "tag_name": tag,
                "name": f"周数据 {week}",
                "body": f"三市场日线（前复权），覆盖 {manifest['start']} ~ {manifest['end']}。\n"
                        f"manifest.json 见附件；用 merger/merger.py 可幂等合并入库。",
            },
            timeout=30,
        )
        r.raise_for_status()
        release = r.json()
        log.info("Release %s 已创建", tag)

    upload_url = release["upload_url"].split("{")[0]
    existing = {a["name"] for a in release.get("assets", [])}

    def _upload(path: Path, content_type: str) -> None:
        if path.name in existing:
            log.info("附件 %s 已存在，跳过", path.name)
            return
        with open(path, "rb") as f:
            r = session.post(
                upload_url,
                params={"name": path.name},
                headers={"Content-Type": content_type},
                data=f,
                timeout=300,
            )
        r.raise_for_status()
        log.info("附件 %s 上传成功", path.name)

    manifest_path = EXPORT_DIR / f"manifest-{week}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _upload(manifest_path, "application/json")
    for p in parquet_paths:
        _upload(p, "application/octet-stream")


def run() -> dict:
    """每周任务入口：导出上周数据；配好 GitHub 则发布 Release。"""
    start, end, week = last_week_range()
    log.info("===== 周导出任务：%s（%s ~ %s） =====", week, start, end)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    files, parquet_paths = {}, []
    for market in MARKETS:
        path, nrows = export_market(market, start, end, EXPORT_DIR)
        files[market] = {"file": path.name, "rows": nrows}
        parquet_paths.append(path)

    manifest = build_manifest(week, start, end, files)
    manifest_path = EXPORT_DIR / f"manifest-{week}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("manifest 已生成：%s", manifest_path.name)

    if config.GITHUB_TOKEN and config.GITHUB_REPO:
        publish_release(week, manifest, parquet_paths)
    else:
        log.warning("未配置 GITHUB_TOKEN / GITHUB_REPO，跳过 GitHub 发布（仅本地导出）")
    return manifest


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        run()
    finally:
        db.close_pool()
