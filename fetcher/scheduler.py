"""调度器入口：APScheduler 常驻进程。

定时（Asia/Shanghai）：
- 每天 05:30  daily_fetch   三市场日线增量拉取
- 每周一 06:10 weekly_export 上周数据导出 + GitHub Release 发布

本地运行：
    cd stock-data && .venv/bin/python -m fetcher.scheduler
手动触发：
    .venv/bin/python -m fetcher.scheduler --run-now daily --market cn
"""
import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from fetcher import config, db
from fetcher.jobs import daily_fetch, weekly_export

log = logging.getLogger(__name__)


def build_scheduler() -> BlockingScheduler:
    sched = BlockingScheduler(timezone=config.TZ)
    # 每天 05:30 拉取（美股已收盘；A股/港股为上一交易日）
    sched.add_job(
        daily_fetch.run, "cron", hour=5, minute=30,
        id="daily_fetch", name="每日拉取",
        misfire_grace_time=3600, max_instances=1,
    )
    # 每周一 06:10 导出上周并发布
    sched.add_job(
        weekly_export.run, "cron", day_of_week="mon", hour=6, minute=10,
        id="weekly_export", name="周导出发布",
        misfire_grace_time=3600, max_instances=1,
    )
    return sched


def main() -> None:
    parser = argparse.ArgumentParser(description="股票数据管道调度器")
    parser.add_argument("--run-now", choices=["daily", "weekly"], default=None,
                        help="立即手动执行一次任务（不启动定时循环）")
    parser.add_argument("--market", choices=["cn", "hk", "us"], default=None,
                        help="配合 --run-now daily，只跑指定市场")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.run_now == "daily":
        log.info("手动触发每日拉取（market=%s）", args.market)
        try:
            daily_fetch.run(market=args.market)
        finally:
            db.close_pool()
        return
    if args.run_now == "weekly":
        log.info("手动触发周导出")
        try:
            weekly_export.run()
        finally:
            db.close_pool()
        return

    sched = build_scheduler()
    for job in sched.get_jobs():
        log.info("已注册定时任务：%s -> %s", job.name, job.trigger)
    try:
        log.info("调度器启动（时区 %s）", config.TZ)
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("调度器退出")
    finally:
        db.close_pool()


if __name__ == "__main__":
    main()
