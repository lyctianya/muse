"""Tushare 增量数据回填（A股 5000积分档）。

用法：
    # 全部（每日指标近10年 + 其余近2年）
    python -m fetcher.jobs.backfill_tushare_extra

    # 只跑某类
    python -m fetcher.jobs.backfill_tushare_extra --only daily_basic
    python -m fetcher.jobs.backfill_tushare_extra --only moneyflow
    python -m fetcher.jobs.backfill_tushare_extra --only dividend
    python -m fetcher.jobs.backfill_tushare_extra --only forecast

    # 断点续跑：从指定日期开始
    python -m fetcher.jobs.backfill_tushare_extra --only daily_basic --from-date 2020-01-01

需要 TUSHARE_TOKEN。幂等 upsert，重跑安全。
"""
import argparse
import logging
import sys
import time

from fetcher import config, db
from fetcher.sources import _tls_patch
from fetcher.sources import tushare_extra as tx

_tls_patch.apply()

log = logging.getLogger("backfill_tushare_extra")

JOBS = {
    "daily_basic": ("每日指标（近10年）", tx.backfill_daily_basic),
    "moneyflow": ("资金流向+停复牌（近2年）", tx.backfill_moneyflow_suspend),
    "dividend": ("分红送股（近2年）", tx.backfill_dividend),
    "forecast": ("业绩预告+快报（近2年）", tx.backfill_forecast_express),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Tushare 增量数据回填")
    ap.add_argument("--only", choices=list(JOBS) + ["all"], default="all",
                    help="只跑哪一类（默认 all）")
    ap.add_argument("--from-date", default="",
                    help="起始日期 YYYY-MM-DD（断点续跑）")
    ap.add_argument("--force", action="store_true",
                    help="忽略水位，强制重跑")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config.require_database_url()
    if not config.TUSHARE_TOKEN:
        raise SystemExit("需要配置 TUSHARE_TOKEN 环境变量")

    from fetcher.sync_freshness import should_skip_job

    names = list(JOBS) if args.only == "all" else [args.only]
    t0 = time.time()
    for name in names:
        label, fn = JOBS[name]
        skip, reason = should_skip_job(name, force=args.force or bool(args.from_date))
        if skip:
            log.info("跳过：%s（%s）", label, reason)
            continue
        log.info("开始：%s", label)
        try:
            fn(args.from_date)
            from fetcher import sync_status as ss
            ss.mark_synced_from_job(name)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s 异常中断：%s", label, exc)
    log.info("全部完成，总耗时 %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
