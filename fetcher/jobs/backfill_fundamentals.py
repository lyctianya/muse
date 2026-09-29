"""A股基本面回填（近 2 年，断点续跑安全）。

用法：
    # 全量回填（Tushare 主源，需 TUSHARE_TOKEN）
    python -m fetcher.jobs.backfill_fundamentals --source tushare

    # 东方财富源（默认，无需 token，但可能被限流）
    python -m fetcher.jobs.backfill_fundamentals --source eastmoney

    # 只抓前 N 只（冒烟测试）
    python -m fetcher.jobs.backfill_fundamentals --source tushare --limit 5

    # 只抓指定股票
    python -m fetcher.jobs.backfill_fundamentals --source tushare --symbols 600519,000001

    # 校验 Tushare token
    python -m fetcher.jobs.backfill_fundamentals --source tushare --check-token

特性：
- 幂等 upsert，重跑安全；单只股票失败不影响其他
- 进度每 50 只打一次日志
- eastmoney 源会先应用 _tls_patch（走 curl_cffi 浏览器指纹）
"""
import argparse
import logging
import sys
import time
from datetime import date

from fetcher import config, db
from fetcher.sources import _tls_patch, cn, cn_fundamentals

_tls_patch.apply()

log = logging.getLogger("backfill_fundamentals")


def _get_cn_symbols() -> list:
    """从库里取 A股现役名单（symbol, name）。"""
    pool = db.get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, name FROM symbols WHERE market='cn' AND active "
            "ORDER BY symbol")
        return [(r[0], r[1]) for r in cur.fetchall()]


def backfill_market_wide() -> None:
    """全市场维度：股权质押快照 + 股东增减持（单个失败不影响另一个）。"""
    t0 = time.time()
    n1 = n2 = 0
    try:
        n1 = cn_fundamentals.upsert_pledge_all()
    except Exception as exc:  # noqa: BLE001
        log.warning("全市场质押失败：%s", exc)
    try:
        n2 = cn_fundamentals.upsert_holder_trade_all()
    except Exception as exc:  # noqa: BLE001
        log.warning("全市场增减持失败：%s", exc)
    log.info("全市场维度完成：质押 %d 条，增减持 %d 条，耗时 %.1fs",
             n1, n2, time.time() - t0)


def backfill_symbols(symbols: list, source: str = "eastmoney",
                     *, force: bool = False) -> None:
    total = len(symbols)
    ok = fail = 0
    t0 = time.time()
    skip_fin = False
    skip_main = False
    if source == "tushare":
        from fetcher.sources import tushare_fundamentals as ts_fund
        # 公司基本信息全市场一次拉取（今日已同步则跳过）
        try:
            ts_fund.upsert_company_info_all(force=force)
        except Exception as exc:  # noqa: BLE001
            log.warning("Tushare 公司基本信息批量拉取失败：%s", exc)
        # 财务三表 + 指标：VIP 按水位增量季度
        try:
            r = ts_fund.backfill_fin_statements_vip(force=force)
            if r.get("skipped"):
                log.info("VIP 三表+指标：水位已覆盖，跳过")
            else:
                log.info("VIP 三表+指标批量完成：%s", r)
            skip_fin = True
        except Exception as exc:  # noqa: BLE001
            log.warning("VIP 三表批量失败，逐只拉取时补：%s", exc)
        # 主营构成：VIP 按水位增量季度
        try:
            n = ts_fund.backfill_main_business_vip(force=force)
            if n == 0 and not force:
                log.info("VIP 主营构成：水位已覆盖或无新季度，跳过")
            else:
                log.info("VIP 主营构成批量完成：%d 行", n)
            skip_main = True
        except Exception as exc:  # noqa: BLE001
            log.warning("VIP 主营构成批量失败，将跳过东财补充（请检查积分/中转）：%s",
                        exc)
            skip_main = True  # 仍不走东财，避免拖死全流程
        # 股东类增量：按报告期水位判断，避免「已有上季数据却因 180 天阈值被重拉」
        # - top_holders：需覆盖最新已结束季度
        # - holder_number：披露滞后，覆盖上一季度即可
        # - pledge_info：大量股票本无质押，不作为「必须重拉」条件
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from fetcher.sources.tushare_fundamentals import (
            _periods, _symbol_max_dates, _to_date,
        )

        periods = _periods()
        q_latest = _to_date(periods[0]) if periods else date.today()
        q_prev = _to_date(periods[1]) if len(periods) > 1 else q_latest

        max_holders = _symbol_max_dates("top_holders", "report_date")
        max_hnum = _symbol_max_dates("holder_number", "report_date")

        def _stale(sym: str) -> bool:
            th = max_holders.get(sym)
            if th is None or (q_latest and th < q_latest):
                return True
            hn = max_hnum.get(sym)
            if hn is None or (q_prev and hn < q_prev):
                return True
            return False

        todo = [(s, n) for s, n in symbols if _stale(s)]
        log.info(
            "股东/户数增量：共 %d 只，跳过已有 %d，待拉 %d "
            "(holders>=%s, hnum>=%s)，workers=%d",
            total, total - len(todo), len(todo),
            q_latest, q_prev, config.TUSHARE_WORKERS,
        )

        _skip_fin = skip_fin
        _skip_main = skip_main

        def _one(pair):
            sym, _name = pair
            return ts_fund.fetch_one(
                sym, skip_fin=_skip_fin, skip_main_business=_skip_main)

        workers = max(1, int(config.TUSHARE_WORKERS))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_one, p): p for p in todo}
            done = 0
            for fut in as_completed(futs):
                done += 1
                try:
                    fut.result()
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    sym, name = futs[fut]
                    log.warning("[%s] %s 基本面抓取异常：%s", sym, name, exc)
                    fail += 1
                if done % 50 == 0 or done == len(todo):
                    log.info("进度 %d/%d（成功 %d，失败 %d），耗时 %.1fs",
                             done, len(todo), ok, fail, time.time() - t0)
        log.info("基本面回填完成：待拉 %d，成功 %d，失败 %d，总耗时 %.1fs",
                 len(todo), ok, fail, time.time() - t0)
        return

    fetch_fn = cn_fundamentals.fetch_one
    for i, (symbol, name) in enumerate(symbols, start=1):
        try:
            fetch_fn(symbol)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] %s 基本面抓取异常：%s", symbol, name, exc)
            fail += 1
        if i % 50 == 0 or i == total:
            log.info("进度 %d/%d（成功 %d，失败 %d），耗时 %.1fs",
                     i, total, ok, fail, time.time() - t0)
    log.info("基本面回填完成：共 %d 只，成功 %d，失败 %d，总耗时 %.1fs",
             total, ok, fail, time.time() - t0)


def main() -> None:
    ap = argparse.ArgumentParser(description="A股基本面回填（近2年）")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 只（0=全部）")
    ap.add_argument("--symbols", default="", help="指定股票，逗号分隔（如 600519,000001）")
    ap.add_argument("--market-wide", action="store_true",
                    help="只跑全市场维度（股权质押+股东增减持，仅 eastmoney 源）")
    ap.add_argument("--source", default="tushare",
                    choices=["eastmoney", "tushare"],
                    help="数据源：tushare（默认，批量+增量）或 eastmoney")
    ap.add_argument("--check-token", action="store_true",
                    help="校验 Tushare token 有效性后退出")
    ap.add_argument("--force", action="store_true",
                    help="忽略 sync_status 水位，强制重拉公司信息/VIP 季度")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config.require_database_url()

    if args.check_token:
        from fetcher.sources import tushare_fundamentals as ts_fund
        r = ts_fund.check_token()
        log.info("Tushare token 校验结果：%s", r)
        return

    if args.source == "tushare" and not config.TUSHARE_TOKEN:
        raise SystemExit("使用 --source tushare 需要配置 TUSHARE_TOKEN 环境变量")

    if args.market_wide:
        if args.source == "tushare":
            log.warning("--market-wide 暂只支持 eastmoney 源，跳过")
            return
        backfill_market_wide()
        return

    if args.symbols:
        symbols = [(s.strip().zfill(6), s.strip().zfill(6))
                   for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = _get_cn_symbols()
        # 名单为空时（如新库）回退到现役名单接口
        if not symbols:
            log.info("库内无名单，从接口拉取现役名单")
            symbols = [(c, n) for c, n in cn.get_symbols()]
    if args.limit:
        symbols = symbols[:args.limit]
    log.info("待抓取：%d 只（数据源=%s%s）",
             len(symbols), args.source, "，强制全量" if args.force else "")
    backfill_symbols(symbols, source=args.source, force=args.force)
    # 全市场维度顺手跑一遍（仅 eastmoney 源）
    if args.source == "eastmoney":
        backfill_market_wide()
    try:
        from fetcher import sync_status as ss
        ss.mark_synced_from_job("fundamentals")
    except Exception as exc:  # noqa: BLE001
        log.warning("刷新 sync_status 失败：%s", exc)


if __name__ == "__main__":
    main()
