"""每日拉取任务：三市场现役名单刷新 + 日线增量拉取。

流程（每个市场）：
1. 拉取现役名单 -> upsert 到 symbols 表；消失的旧代码标记 active=FALSE
2. 对每只股票：查库内最新交易日 -> 从该日期增量拉取 -> 幂等 upsert
3. 前复权除权除息检测：新数据与库中重叠日期的收盘价对比，
   偏差超过阈值 -> 判定发生除权除息 -> 该股票全历史重拉覆盖

多线程并发拉取（默认 8 线程），写入走连接池，任务重跑安全。
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Optional

from fetcher import config, db
from fetcher.sources import cn, hk, us

log = logging.getLogger(__name__)

# 全历史回填起点（首次运行无数据时使用）
FULL_HISTORY_START = date(1990, 1, 1)

MARKETS = {
    "cn": {"module": cn, "label": "A股"},
    "hk": {"module": hk, "label": "港股"},
    "us": {"module": us, "label": "美股"},
}


def _needs_full_refetch(market: str, symbol: str, bars: list, max_date: date) -> bool:
    """前复权重叠校验：比较新拉数据与库中重叠日期的收盘价。

    前复权以最新交易日为锚点，除权除息会导致历史价格整体变化。
    若重叠日期收盘价偏差超过阈值，返回 True（需全历史重拉）。
    """
    if not bars or max_date is None:
        return False
    db_closes = db.get_db_closes(market, symbol, max_date)
    if not db_closes:
        return False
    for bar in bars:
        td = bar["trade_date"]
        old_close = db_closes.get(td)
        if old_close and old_close != 0 and bar["close"]:
            drift = abs(bar["close"] / old_close - 1)
            if drift > config.ADJUST_SPLIT_THRESHOLD:
                log.warning(
                    "[%s:%s] 检测到除权除息（%s 收盘价 %.4f -> %.4f，漂移 %.2f%%），"
                    "触发全历史重拉",
                    market, symbol, td, old_close, bar["close"], drift * 100,
                )
                return True
    return False


def _fetch_one(market: str, module, currency: str, symbol: str) -> tuple:
    """拉取单只股票，返回 (symbol, 新增/更新条数, 状态说明)。"""
    t0 = time.time()
    try:
        max_date: Optional[date] = db.get_max_trade_date(market, symbol)
        start = max_date or FULL_HISTORY_START
        bars = module.fetch_bars(symbol, start)
        if not bars:
            return symbol, 0, "无新数据"

        # 除权除息检测 -> 全历史重拉覆盖
        if _needs_full_refetch(market, symbol, bars, max_date):
            bars = module.fetch_bars(symbol, FULL_HISTORY_START)

        for b in bars:
            b["market"] = market
            b["symbol"] = symbol  # 某些源（如 yfinance）返回的 bar 不带 symbol
            b["currency"] = currency
        n = db.upsert_bars(bars)
        return symbol, n, f"ok（{len(bars)}条，{time.time()-t0:.1f}s）"
    except Exception as exc:  # noqa: BLE001 - 单只失败不影响整体
        log.error("[%s:%s] 拉取失败：%s", market, symbol, exc)
        return symbol, 0, f"失败：{exc}"


def fetch_market(market: str, workers: Optional[int] = None) -> dict:
    """拉取单个市场，返回统计 {total, ok, empty, failed, bars}。"""
    workers = workers or config.FETCH_WORKERS
    module = MARKETS[market]["module"]
    label = MARKETS[market]["label"]
    currency = module.CURRENCY

    log.info("===== 开始拉取 %s（%s） =====", label, market)

    # 1. 刷新现役名单
    symbols = module.get_symbols()
    db.upsert_symbols(market, symbols, currency)
    # 标记退市/消失的
    old_active = set(db.get_active_symbols(market))
    fresh = {s for s, _ in symbols}
    db.mark_inactive(market, old_active - fresh)

    # 2. 并发拉取日线
    stats = {"total": len(symbols), "ok": 0, "empty": 0, "failed": 0, "bars": 0}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_fetch_one, market, module, currency, sym): sym
            for sym, _ in symbols
        }
        done = 0
        for fut in as_completed(futures):
            sym, n, msg = fut.result()
            done += 1
            if msg.startswith("ok"):
                stats["ok"] += 1
                stats["bars"] += n
            elif msg == "无新数据":
                stats["empty"] += 1
            else:
                stats["failed"] += 1
            if done % 500 == 0 or done == stats["total"]:
                log.info("[%s] 进度 %d/%d（成功 %d，空 %d，失败 %d）",
                         market, done, stats["total"],
                         stats["ok"], stats["empty"], stats["failed"])
    log.info("===== %s 拉取完成：%s =====", label, stats)
    return stats


def run(market: Optional[str] = None, workers: Optional[int] = None) -> dict:
    """每日任务入口。market 为 None 时拉取全部三市场。"""
    targets = [market] if market else list(MARKETS)
    result = {}
    for m in targets:
        if m not in MARKETS:
            log.error("未知市场：%s（可选 cn/hk/us）", m)
            continue
        result[m] = fetch_market(m, workers=workers)
    return result


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="每日拉取任务")
    parser.add_argument("--market", choices=["cn", "hk", "us"], default=None,
                        help="只拉取指定市场，默认全部")
    parser.add_argument("--workers", type=int, default=None, help="并发线程数")
    args = parser.parse_args()
    try:
        run(market=args.market, workers=args.workers)
    finally:
        db.close_pool()
