"""从业务表扫描并写入 sync_status（首次部署或水位不准时用）。

用法：
    python -m fetcher.jobs.refresh_sync_status
    python -m fetcher.jobs.refresh_sync_status --only daily_basic,moneyflow
"""
import argparse
import logging
import sys

from fetcher import config, sync_status as ss

log = logging.getLogger("refresh_sync_status")


def main() -> None:
    ap = argparse.ArgumentParser(description="刷新 sync_status 水位表")
    ap.add_argument(
        "--only", default="",
        help="逗号分隔表名；默认刷新注册表全部",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config.require_database_url()

    if args.only.strip():
        tables = [x.strip() for x in args.only.split(",") if x.strip()]
        results = ss.refresh_tables(tables)
    else:
        results = ss.refresh_all()

    ok = sum(1 for r in results if r.get("ok"))
    missing = sum(1 for r in results if r.get("missing"))
    for r in results:
        if r.get("ok"):
            log.info("%s  rows=%s latest=%s%s",
                     r["table"], r.get("rows"), r.get("latest_date"),
                     " (表缺失)" if r.get("missing") else "")
        else:
            log.warning("%s 失败：%s", r.get("table"), r.get("error"))
    log.info("完成：%d/%d 成功，表缺失 %d", ok, len(results), missing)


if __name__ == "__main__":
    main()
