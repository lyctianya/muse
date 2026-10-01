"""交易日历缓存：让新鲜度判定识别节假日休市。

trade_calendar 表缓存 Tushare trade_cal（SSE 上交所口径）；
last_trading_day() 供 sync_freshness.needs_update 使用。

缓存未命中时尝试从 API 拉取（走中转站配置），失败则退化为
工作日启发式（与旧行为一致，不抛异常）。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from fetcher import config, db

log = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS trade_calendar (
    cal_date DATE PRIMARY KEY,
    is_open  BOOLEAN NOT NULL
);
"""

# 向前回看天数：覆盖春节/国庆等长假
LOOKBACK_DAYS = 40


def ensure_table() -> None:
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(DDL)
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("建 trade_calendar 表失败：%s", exc)


def _fetch_and_cache(start: date, end: date) -> bool:
    """从 Tushare 拉取日历并缓存；成功返回 True。"""
    try:
        from fetcher.sources.tushare_fundamentals import _throttle, _ts
    except Exception as exc:  # noqa: BLE001
        log.warning("交易日历：tushare 模块不可用：%s", exc)
        return False
    try:
        if not config.TUSHARE_TOKEN:
            return False
        _throttle()
        pro = _ts()
        df = pro.trade_cal(exchange="SSE",
                           start_date=start.strftime("%Y%m%d"),
                           end_date=end.strftime("%Y%m%d"),
                           fields="cal_date,is_open")
        if df is None or df.empty:
            return False
        rows = [(r["cal_date"], str(r["is_open"]) == "1")
                for _, r in df.iterrows()]
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO trade_calendar (cal_date, is_open) VALUES (%s, %s) "
                "ON CONFLICT (cal_date) DO UPDATE SET is_open = EXCLUDED.is_open",
                rows,
            )
            conn.commit()
        log.info("交易日历已缓存：%s ~ %s，共 %d 天", start, end, len(rows))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("交易日历拉取失败：%s", exc)
        return False


def _from_cache(ref: date) -> date | None:
    """从缓存找 <= ref 的最近交易日；无覆盖返回 None。"""
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(cal_date) FROM trade_calendar "
                "WHERE cal_date <= %s AND is_open",
                (ref,),
            )
            row = cur.fetchone()
            if row and row[0]:
                # 确认缓存覆盖了 ref 当天（否则可能是过期缓存）
                cur.execute("SELECT MAX(cal_date) FROM trade_calendar")
                max_cached = cur.fetchone()[0]
                if max_cached and max_cached >= ref:
                    return row[0]
    except Exception as exc:  # noqa: BLE001
        log.warning("读交易日历缓存失败：%s", exc)
    return None


def _weekday_fallback(ref: date) -> date:
    """退化：周一~周五视为交易日。"""
    d = ref
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def last_trading_day(ref: date | None = None) -> date:
    """<= ref 的最近交易日（含 ref 当天）。"""
    ref = ref or date.today()
    ensure_table()
    hit = _from_cache(ref)
    if hit:
        return hit
    # 缓存未命中：拉取近 40 天
    start = ref - timedelta(days=LOOKBACK_DAYS)
    if _fetch_and_cache(start, ref):
        hit = _from_cache(ref)
        if hit:
            return hit
    return _weekday_fallback(ref)
