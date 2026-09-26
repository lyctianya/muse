"""近 10 年历史数据回填（断点续跑安全）。

用法：
    python -m fetcher.jobs.backfill --market us --start 2016-09-26 --workers 6
    python -m fetcher.jobs.backfill --market cn --start 2016-09-26
    python -m fetcher.jobs.backfill --market hk --start 2016-09-26

特性：
- 幂等 upsert；每个 symbol 独立事务提交（小批次，无长事务）
- 断点续跑：已入库的 symbol 下次从库内最大交易日继续，空跑很快跳过
- 进度每 200 只打一次日志；分市场统计（symbol 数/行数/耗时）写日志文件
- 会先应用 _tls_patch（eastmoney/bse.cn 走 curl_cffi 浏览器指纹）
- 美股直走 yfinance（Stooq 在本机网络下不通，跳过可省去每次的重试等待）
"""
import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from fetcher import config, db
from fetcher.sources import _tls_patch, cn, hk, us

_tls_patch.apply()

log = logging.getLogger("backfill")

START_DEFAULT = "2016-09-26"


def _fetch_us_yfinance(symbol: str, start: date, end: date) -> list:
    """美股回填专用：直走 yfinance（跳过已确认不通的 Stooq）。"""
    return us._fetch_yfinance(symbol, start, end)


MARKETS = {
    "cn": {"module": cn, "label": "A股", "fetch": lambda m, s, a, b: m.fetch_bars(s, a, b)},
    "hk": {"module": hk, "label": "港股", "fetch": lambda m, s, a, b: m.fetch_bars(s, a, b)},
    "us": {"module": us, "label": "美股", "fetch": lambda m, s, a, b: _fetch_us_yfinance(s, a, b)},
}


def _backfill_one(market: str, module, fetch_fn, currency: str,
                  symbol: str, name: str, start: date, end: date) -> tuple:
    """回填单只股票，返回 (symbol, 行数, 状态)。"""
    t0 = time.time()
    try:
        max_date = db.get_max_trade_date(market, symbol)
        eff_start = max(max_date, start) if max_date else start
        if max_date and max_date >= end:
            return symbol, 0, "已是最新，跳过"
        bars = fetch_fn(module, symbol, eff_start, end)
        if not bars:
            return symbol, 0, "无数据"
        for b in bars:
            b["market"] = market
            b["symbol"] = symbol  # 某些源（如 yfinance）返回的 bar 不带 symbol
            b["currency"] = currency
        n = db.upsert_bars(bars)
        return symbol, n, f"ok（{len(bars)}条，{time.time()-t0:.1f}s）"
    except Exception as exc:  # noqa: BLE001
        log.error("[%s:%s] 回填失败：%s", market, symbol, exc)
        return symbol, 0, f"失败：{exc}"


def backfill_market(market: str, start: date, end: date,
                    workers: int = 8) -> dict:
    """回填单个市场，返回统计。"""
    module = MARKETS[market]["module"]
    label = MARKETS[market]["label"]
    fetch_fn = MARKETS[market]["fetch"]
    currency = module.CURRENCY
    t_start = time.time()

    log.info("===== 开始回填 %s（%s），区间 %s ~ %s =====", label, market, start, end)

    symbols = module.get_symbols()
    db.upsert_symbols(market, symbols, currency)
    old_active = set(db.get_active_symbols(market))
    db.mark_inactive(market, old_active - {s for s, _ in symbols})

    stats = {"total": len(symbols), "ok": 0, "empty": 0, "skipped": 0,
             "failed": 0, "bars": 0}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_backfill_one, market, module, fetch_fn, currency,
                        sym, name, start, end): sym
            for sym, name in symbols
        }
        done = 0
        for fut in as_completed(futures):
            sym, n, msg = fut.result()
            done += 1
            if msg.startswith("ok"):
                stats["ok"] += 1
                stats["bars"] += n
            elif msg == "无数据":
                stats["empty"] += 1
            elif msg.startswith("已是最新"):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1
            if done % 200 == 0 or done == stats["total"]:
                log.info("[%s] 进度 %d/%d（成功 %d，空 %d，跳过 %d，失败 %d，累计 %d 行）",
                         market, done, stats["total"], stats["ok"],
                         stats["empty"], stats["skipped"], stats["failed"],
                         stats["bars"])
    stats["elapsed_s"] = round(time.time() - t_start, 1)
    log.info("===== %s 回填完成：%s =====", label, stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="近 10 年历史数据回填")
    parser.add_argument("--market", choices=["cn", "hk", "us"], required=True)
    parser.add_argument("--start", default=START_DEFAULT,
                        help="回填起始日期 YYYY-MM-DD，默认 2016-09-26")
    parser.add_argument("--end", default=None,
                        help="回填结束日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--log-dir", default="logs",
                        help="日志目录（相对项目根目录）")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else date.today()

    log_dir = Path(config.ROOT) / args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"backfill_{args.market}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    log.info("日志文件：%s", log_file)
    try:
        stats = backfill_market(args.market, start, end, args.workers)
        log.info("FINAL %s: %s", args.market, stats)
    finally:
        db.close_pool()


if __name__ == "__main__":
    main()
