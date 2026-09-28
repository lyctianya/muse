"""Tushare 全量接口回填（A股 5000积分档，17 张表）。

用法：
    # 全部
    python -m fetcher.jobs.backfill_tushare_full

    # 只跑某类
    python -m fetcher.jobs.backfill_tushare_full --only mainbz
    python -m fetcher.jobs.backfill_tushare_full --only top_list
    python -m fetcher.jobs.backfill_tushare_full --only index

    # 断点续跑
    python -m fetcher.jobs.backfill_tushare_full --only stk_limit --from-date 2025-01-01

需要 TUSHARE_TOKEN。幂等 upsert。
"""
import argparse
import logging
import sys
import time

from fetcher import config
from fetcher.sources import _tls_patch
from fetcher.sources import tushare_full as tf

_tls_patch.apply()

log = logging.getLogger("backfill_tushare_full")


def _backfill_index_info(from_date: str = "") -> None:
    tf.backfill_index_basic()
    tf.backfill_index_weight(from_date)
    tf.backfill_index_member()


JOBS = {
    # 批量/一次性（快）
    "company_detail": ("公司详细信息", tf.backfill_company_detail),
    "namechange": ("股票曾用名", tf.backfill_namechange),
    "new_share": ("IPO新股", tf.backfill_new_share),
    "disclosure": ("财报披露计划", tf.backfill_disclosure_date),
    "index": ("指数日线（近10年）", tf.backfill_index_daily),
    "hsgt_flow": ("沪深港通资金流", tf.backfill_moneyflow_hsgt),
    "hsgt_top10": ("陆股通十大成交股", tf.backfill_hsgt_top10),
    "margin": ("融资融券", tf.backfill_margin),
    # 按交易日（中）
    "top_list": ("龙虎榜", tf.backfill_top_list),
    "stk_limit": ("涨跌停（近2年）", tf.backfill_stk_limit),
    # 逐只（慢，增量跳过已有）
    "mainbz": ("主营业务构成", tf.backfill_mainbz),
    "fina_audit": ("审计意见", tf.backfill_fina_audit),
    "managers": ("管理层", tf.backfill_managers),
    "share_float": ("限售解禁", tf.backfill_share_float),
    # 按交易日（中）
    "block_trade": ("大宗交易", tf.backfill_block_trade),
    # 15000积分档补全
    "adj_factor": ("复权因子（近10年，按日）", tf.backfill_adj_factor),
    "holdertrade": ("股东增减持（按公告日）", tf.backfill_holdertrade),
    "daily_ts": ("A股日线（近10年）", tf.backfill_daily_ts),
    "repurchase": ("股票回购", tf.backfill_repurchase),
    "pledge_detail": ("质押明细（逐只）", tf.backfill_pledge_detail),
    "index_info": ("指数基本信息/权重/成分", _backfill_index_info),
    "cyq_perf": ("每日筹码分布（逐只）", tf.backfill_cyq_perf),
    "hk_hold": ("沪深港股通持股", tf.backfill_hk_hold),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Tushare 全量接口回填")
    ap.add_argument("--only", choices=list(JOBS) + ["all"], default="all")
    ap.add_argument("--from-date", default="",
                    help="强制起始日期 YYYY-MM-DD；默认按库内 max(日期) 增量续跑")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config.require_database_url()
    if not config.TUSHARE_TOKEN:
        raise SystemExit("需要配置 TUSHARE_TOKEN 环境变量")

    names = list(JOBS) if args.only == "all" else [args.only]
    t0 = time.time()
    for name in names:
        label, fn = JOBS[name]
        log.info("开始：%s", label)
        try:
            # 只有支持 from_date 的才传
            if name in ("top_list", "stk_limit", "index", "hsgt_flow",
                        "hsgt_top10", "margin", "block_trade",
                        "daily_ts", "repurchase", "hk_hold", "index_info",
                        "adj_factor", "holdertrade", "pledge_detail",
                        "disclosure"):
                fn(args.from_date)
            else:
                fn()
        except Exception as exc:  # noqa: BLE001
            log.warning("%s 异常中断：%s", label, exc)
    log.info("全部完成，总耗时 %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
