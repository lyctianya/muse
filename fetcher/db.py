"""数据库访问层：psycopg3 连接池 + 幂等 upsert 封装。

所有写入都使用 INSERT ... ON CONFLICT DO UPDATE，
任务重跑 / 断点续跑都是安全的。
"""
import logging
from datetime import date
from typing import Iterable, Mapping, Optional

from psycopg_pool import ConnectionPool

from fetcher import config

log = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """全局连接池（懒加载，线程安全）。"""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            config.require_database_url(),
            min_size=2,
            max_size=16,
            kwargs={"autocommit": True},
        )
        log.info("数据库连接池已创建")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


# ---------------- 股票名单 ----------------

_UPSERT_SYMBOL = """
INSERT INTO symbols (market, symbol, name, currency, active)
VALUES (%(market)s, %(symbol)s, %(name)s, %(currency)s, TRUE)
ON CONFLICT (market, symbol) DO UPDATE SET
    name = EXCLUDED.name,
    currency = EXCLUDED.currency,
    active = TRUE
"""


def upsert_symbols(market: str, symbols: Iterable[tuple], currency: str) -> int:
    """刷新市场现役名单。symbols: [(symbol, name), ...]。返回写入条数。"""
    rows = [
        {"market": market, "symbol": s, "name": n, "currency": currency}
        for s, n in symbols
    ]
    if not rows:
        return 0
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(_UPSERT_SYMBOL, rows)
    log.info("[%s] 名单已刷新：%d 只", market, len(rows))
    return len(rows)


def mark_inactive(market: str, symbols: Iterable[str]) -> int:
    """把不再出现在现役名单中的股票标记为 active=FALSE（软删除，不删行情）。"""
    symbols = list(symbols)
    if not symbols:
        return 0
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE symbols SET active = FALSE "
                "WHERE market = %s AND symbol = ANY(%s) AND active = TRUE",
                (market, symbols),
            )
            n = cur.rowcount
    if n:
        log.info("[%s] %d 只股票标记为退市/不活跃", market, n)
    return n


def get_active_symbols(market: str) -> list:
    """取某市场全部现役股票代码。"""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol FROM symbols WHERE market = %s AND active = TRUE",
                (market,),
            )
            return [r[0] for r in cur.fetchall()]


# ---------------- 日线行情 ----------------

_UPSERT_BAR = """
INSERT INTO daily_bars
    (market, symbol, trade_date, open, high, low, close, volume, amount, pct_change, currency)
VALUES
    (%(market)s, %(symbol)s, %(trade_date)s, %(open)s, %(high)s, %(low)s,
     %(close)s, %(volume)s, %(amount)s, %(pct_change)s, %(currency)s)
ON CONFLICT (market, symbol, trade_date) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    amount = EXCLUDED.amount,
    pct_change = EXCLUDED.pct_change,
    currency = EXCLUDED.currency,
    updated_at = now()
"""


def upsert_bars(rows: Iterable[Mapping]) -> int:
    """批量写入日线（幂等）。rows: 每行含 market/symbol/trade_date/open/high/low/
    close/volume/amount/pct_change/currency。返回写入条数。

    兜底：pct_change 为空时，用库中前一交易日收盘价补算
    （增量抓取批次首日无 prev_close 的常见情况）。
    """
    rows = list(rows)
    if not rows:
        return 0
    _fill_missing_pct_change(rows)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(_UPSERT_BAR, rows)
    return len(rows)


def _fill_missing_pct_change(rows: list) -> None:
    """原地补算缺失的 pct_change。"""
    missing = [r for r in rows
               if r.get("pct_change") is None and r.get("close")]
    if not missing:
        return
    # 按 (market, symbol, 最早缺失日期) 分组，一次查出各自的前收
    keys = {}
    for r in missing:
        k = (r["market"], r["symbol"])
        td = r["trade_date"]
        if k not in keys or td < keys[k]:
            keys[k] = td
    prev = {}
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            for (market, symbol), min_date in keys.items():
                cur.execute(
                    "SELECT close FROM daily_bars"
                    " WHERE market = %s AND symbol = %s AND trade_date < %s"
                    " ORDER BY trade_date DESC LIMIT 1",
                    (market, symbol, min_date),
                )
                row = cur.fetchone()
                if row and row[0]:
                    prev[(market, symbol)] = float(row[0])
    # 按日期排序后链式补算（同 symbol 多天缺失时也能递推）
    missing.sort(key=lambda r: (r["market"], r["symbol"], r["trade_date"]))
    last_close: dict = {}
    for r in missing:
        k = (r["market"], r["symbol"])
        pc = last_close.get(k, prev.get(k))
        close = float(r["close"])
        if pc:
            r["pct_change"] = round((close / pc - 1) * 100, 4)
        last_close[k] = close


def get_max_trade_date(market: str, symbol: str) -> Optional[date]:
    """某股票库内最新交易日（用于增量拉取起点）。"""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT max(trade_date) FROM daily_bars WHERE market = %s AND symbol = %s",
                (market, symbol),
            )
            row = cur.fetchone()
            return row[0] if row else None


def get_db_closes(market: str, symbol: str, start: date) -> dict:
    """取某股票 start（含）之后库中已有的 {trade_date: close}，
    用于前复权重叠校验。"""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, close FROM daily_bars "
                "WHERE market = %s AND symbol = %s AND trade_date >= %s",
                (market, symbol, start),
            )
            return {r[0]: r[1] for r in cur.fetchall()}
