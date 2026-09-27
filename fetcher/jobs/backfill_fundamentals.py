"""A股基本面回填（近 2 年，断点续跑安全）。

用法：
    # 全量回填（A股现役名单，逐只抓取基本面）
    python -m fetcher.jobs.backfill_fundamentals

    # 只抓前 N 只（冒烟测试）
    python -m fetcher.jobs.backfill_fundamentals --limit 5

    # 只抓指定股票
    python -m fetcher.jobs.backfill_fundamentals --symbols 600519,000001

    # 全市场维度（股权质押快照 + 股东增减持）
    python -m fetcher.jobs.backfill_fundamentals --market-wide

特性：
- 幂等 upsert，重跑安全；单只股票失败不影响其他
- 进度每 50 只打一次日志
- 会先应用 _tls_patch（eastmoney 走 curl_cffi 浏览器指纹）
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


def backfill_symbols(symbols: list) -> None:
    total = len(symbols)
    ok = fail = 0
    t0 = time.time()
    for i, (symbol, name) in enumerate(symbols, start=1):
        try:
            r = cn_fundamentals.fetch_one(symbol)
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
                    help="只跑全市场维度（股权质押+股东增减持）")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config.require_database_url()

    if args.market_wide:
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
    log.info("待抓取：%d 只", len(symbols))
    backfill_symbols(symbols)
    # 全市场维度顺手跑一遍
    backfill_market_wide()


if __name__ == "__main__":
    main()
