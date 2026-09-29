"""审计 sync_status：哪些回填任务已覆盖、哪些还需拉。

用法：
    python -m fetcher.jobs.audit_sync_status
    python -m fetcher.jobs.audit_sync_status --refresh   # 先从业务表重扫水位
"""
import argparse
import logging
import sys

from fetcher import config, sync_status as ss
from fetcher.sync_freshness import PER_SYMBOL_JOBS, audit_report, format_audit
from fetcher.sync_registry import JOB_TABLES

log = logging.getLogger("audit_sync_status")


def main() -> None:
    ap = argparse.ArgumentParser(description="审计同步水位 / 任务跳过计划")
    ap.add_argument("--refresh", action="store_true",
                    help="先从业务表重扫 sync_status")
    ap.add_argument("--jobs", default="",
                    help="逗号分隔任务名；默认全部 JOB_TABLES")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config.require_database_url()

    if args.refresh:
        log.info("重扫 sync_status …")
        ss.refresh_all()

    jobs = None
    if args.jobs.strip():
        jobs = [x.strip() for x in args.jobs.split(",") if x.strip()]
        unknown = [j for j in jobs if j not in JOB_TABLES]
        if unknown:
            raise SystemExit(f"未知任务：{unknown}；可选：{sorted(JOB_TABLES)}")

    rows = audit_report(jobs=jobs)
    print(format_audit(rows))
    skip_n = sum(1 for r in rows if r.get("skip_ok"))
    pull_n = sum(1 for r in rows if not r.get("skip_ok") and r["job"] not in PER_SYMBOL_JOBS)
    internal_n = len(rows) - skip_n - pull_n
    print()
    print(f"合计 {len(rows)} 个任务：可跳过 {skip_n}，需拉取 {pull_n}，"
          f"逐只内部增量 {internal_n}")


if __name__ == "__main__":
    main()
