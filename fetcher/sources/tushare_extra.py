"""Tushare Pro 增量数据抓取（A股 5000积分档）。

6 张表，按交易日/季度批量拉取（比逐只股票高效 10 倍以上）：
- daily_basic  每日指标（PE/PB/市值/换手率）  近10年，按交易日
- moneyflow    个股资金流向                  近2年，按交易日
- suspend      停复牌                          近2年，按交易日
- dividend     分红送股                        近2年，按公告日
- forecast     业绩预告                        近2年，按季度
- express      业绩快报                        近2年，按季度

幂等 upsert，可断点续跑（--from-date 指定起始日期）。
"""
import logging
import time
from datetime import date, timedelta

import pandas as pd

from fetcher import config, db
from fetcher.sources.tushare_fundamentals import (
    _call, _cutoff, _plain, _to_date, _to_float, _row_json,
)

log = logging.getLogger(__name__)

TEN_YEARS_AGO = date.today().replace(year=date.today().year - 10)


def _trade_days(start: date, end: date) -> list:
    """交易日列表（YYYYMMDD 字符串）。"""
    df = _call("trade_cal", exchange="SSE",
               start_date=start.strftime("%Y%m%d"),
               end_date=end.strftime("%Y%m%d"),
               fields="cal_date,is_open")
    if df is None or df.empty:
        return []
    return [str(r["cal_date"]) for _, r in df.iterrows() if r["is_open"] == 1]


def _upsert_daily_basic(trade_date: str) -> int:
    try:
        df = _call("daily_basic", trade_date=trade_date,
                   fields="ts_code,trade_date,pe,pe_ttm,pb,ps,ps_ttm,"
                          "dv_ratio,dv_ttm,turnover_rate,volume_ratio,"
                          "total_mv,circ_mv")
    except Exception as exc:  # noqa: BLE001
        log.warning("daily_basic %s 失败：%s", trade_date, exc)
        return 0
    if df is None or df.empty:
        return 0
    td = _to_date(trade_date)
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            cur.execute(
                """INSERT INTO daily_basic
                   (market, symbol, trade_date, pe, pe_ttm, pb, ps, ps_ttm,
                    dv_ratio, dv_ttm, turnover_rate, volume_ratio,
                    total_mv, circ_mv)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, trade_date) DO UPDATE SET
                     pe=EXCLUDED.pe, pe_ttm=EXCLUDED.pe_ttm, pb=EXCLUDED.pb,
                     ps=EXCLUDED.ps, ps_ttm=EXCLUDED.ps_ttm,
                     dv_ratio=EXCLUDED.dv_ratio, dv_ttm=EXCLUDED.dv_ttm,
                     turnover_rate=EXCLUDED.turnover_rate,
                     volume_ratio=EXCLUDED.volume_ratio,
                     total_mv=EXCLUDED.total_mv, circ_mv=EXCLUDED.circ_mv,
                     updated_at=now()""",
                (symbol, td,
                 _to_float(row.get("pe")), _to_float(row.get("pe_ttm")),
                 _to_float(row.get("pb")), _to_float(row.get("ps")),
                 _to_float(row.get("ps_ttm")),
                 _to_float(row.get("dv_ratio")), _to_float(row.get("dv_ttm")),
                 _to_float(row.get("turnover_rate")),
                 _to_float(row.get("volume_ratio")),
                 # 万元 -> 元
                 (_to_float(row.get("total_mv")) or 0) * 10000 or None,
                 (_to_float(row.get("circ_mv")) or 0) * 10000 or None))
            n += 1
    return n


def _upsert_moneyflow(trade_date: str) -> int:
    try:
        df = _call("moneyflow", trade_date=trade_date,
                   fields="ts_code,trade_date,buy_sm_amount,sell_sm_amount,"
                          "buy_md_amount,sell_md_amount,buy_lg_amount,"
                          "sell_lg_amount,buy_elg_amount,sell_elg_amount,"
                          "net_mf_amount")
    except Exception as exc:  # noqa: BLE001
        log.warning("moneyflow %s 失败：%s", trade_date, exc)
        return 0
    if df is None or df.empty:
        return 0
    td = _to_date(trade_date)
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            cur.execute(
                """INSERT INTO moneyflow
                   (market, symbol, trade_date, buy_sm_amount, sell_sm_amount,
                    buy_md_amount, sell_md_amount, buy_lg_amount, sell_lg_amount,
                    buy_elg_amount, sell_elg_amount, net_mf_amount)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, trade_date) DO UPDATE SET
                     buy_sm_amount=EXCLUDED.buy_sm_amount,
                     sell_sm_amount=EXCLUDED.sell_sm_amount,
                     buy_md_amount=EXCLUDED.buy_md_amount,
                     sell_md_amount=EXCLUDED.sell_md_amount,
                     buy_lg_amount=EXCLUDED.buy_lg_amount,
                     sell_lg_amount=EXCLUDED.sell_lg_amount,
                     buy_elg_amount=EXCLUDED.buy_elg_amount,
                     sell_elg_amount=EXCLUDED.sell_elg_amount,
                     net_mf_amount=EXCLUDED.net_mf_amount,
                     updated_at=now()""",
                (symbol, td,
                 _to_float(row.get("buy_sm_amount")),
                 _to_float(row.get("sell_sm_amount")),
                 _to_float(row.get("buy_md_amount")),
                 _to_float(row.get("sell_md_amount")),
                 _to_float(row.get("buy_lg_amount")),
                 _to_float(row.get("sell_lg_amount")),
                 _to_float(row.get("buy_elg_amount")),
                 _to_float(row.get("sell_elg_amount")),
                 _to_float(row.get("net_mf_amount"))))
            n += 1
    return n


def _upsert_suspend(trade_date: str) -> int:
    try:
        df = _call("suspend_d", trade_date=trade_date,
                   fields="ts_code,trade_date,suspend_date,resume_date,"
                          "ann_date,suspend_reason")
    except Exception as exc:  # noqa: BLE001
        log.warning("suspend_d %s 失败：%s", trade_date, exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            sd = _to_date(row.get("suspend_date"))
            if not sd:
                continue
            cur.execute(
                """INSERT INTO suspend
                   (market, symbol, suspend_date, resume_date, ann_date,
                    suspend_reason)
                   VALUES ('cn', %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, suspend_date) DO UPDATE SET
                     resume_date=EXCLUDED.resume_date,
                     ann_date=EXCLUDED.ann_date,
                     suspend_reason=EXCLUDED.suspend_reason""",
                (symbol, sd, _to_date(row.get("resume_date")),
                 _to_date(row.get("ann_date")),
                 str(row.get("suspend_reason") or "")))
            n += 1
    return n


def _upsert_dividend(ann_date: str) -> int:
    try:
        df = _call("dividend", ann_date=ann_date,
                   fields="ts_code,ann_date,end_date,div_proc,stk_div,"
                          "stk_bo_rate,stk_co_rate,cash_div,cash_div_tax,"
                          "record_date,ex_date,pay_date")
    except Exception as exc:  # noqa: BLE001
        log.warning("dividend %s 失败：%s", ann_date, exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            ad, ed = _to_date(row.get("ann_date")), _to_date(row.get("end_date"))
            if not ad or not ed:
                continue
            cur.execute(
                """INSERT INTO dividend
                   (market, symbol, ann_date, end_date, div_proc, stk_div,
                    stk_bo_rate, stk_co_rate, cash_div, cash_div_tax,
                    record_date, ex_date, pay_date, data)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s::jsonb)
                   ON CONFLICT (market, symbol, ann_date, end_date) DO UPDATE SET
                     div_proc=EXCLUDED.div_proc, stk_div=EXCLUDED.stk_div,
                     stk_bo_rate=EXCLUDED.stk_bo_rate,
                     stk_co_rate=EXCLUDED.stk_co_rate,
                     cash_div=EXCLUDED.cash_div,
                     cash_div_tax=EXCLUDED.cash_div_tax,
                     record_date=EXCLUDED.record_date, ex_date=EXCLUDED.ex_date,
                     pay_date=EXCLUDED.pay_date, data=EXCLUDED.data""",
                (symbol, ad, ed, str(row.get("div_proc") or ""),
                 _to_float(row.get("stk_div")), _to_float(row.get("stk_bo_rate")),
                 _to_float(row.get("stk_co_rate")), _to_float(row.get("cash_div")),
                 _to_float(row.get("cash_div_tax")),
                 _to_date(row.get("record_date")), _to_date(row.get("ex_date")),
                 _to_date(row.get("pay_date")), _row_json(row)))
            n += 1
    return n


def _quarters(start: date, end: date) -> list:
    """起止日期内的季度 (start_yyyymmdd, end_yyyymmdd) 列表。"""
    out = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        q_end_m = ((m - 1) // 3 + 1) * 3
        q_start = date(y, ((q_end_m - 1) // 3) * 3 + 1, 1)
        # 季度末
        if q_end_m == 12:
            q_end = date(y, 12, 31)
        else:
            q_end = date(y, q_end_m + 1, 1) - timedelta(days=1)
        s = max(q_start, start).strftime("%Y%m%d")
        e = min(q_end, end).strftime("%Y%m%d")
        if s <= e:
            out.append((s, e))
        # 下一季度
        m = q_end_m + 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _upsert_forecast(q_start: str, q_end: str) -> int:
    try:
        df = _call("forecast", start_date=q_start, end_date=q_end,
                   fields="ts_code,ann_date,end_date,type,p_change_min,"
                          "p_change_max,net_profit_min,net_profit_max,"
                          "last_parent_net")
    except Exception as exc:  # noqa: BLE001
        log.warning("forecast %s-%s 失败：%s", q_start, q_end, exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            ad, ed = _to_date(row.get("ann_date")), _to_date(row.get("end_date"))
            if not ad or not ed:
                continue
            cur.execute(
                """INSERT INTO forecast
                   (market, symbol, ann_date, end_date, ptype,
                    net_profit_min, net_profit_max, last_parent_net, data)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, ann_date, end_date) DO UPDATE SET
                     ptype=EXCLUDED.ptype,
                     net_profit_min=EXCLUDED.net_profit_min,
                     net_profit_max=EXCLUDED.net_profit_max,
                     last_parent_net=EXCLUDED.last_parent_net,
                     data=EXCLUDED.data""",
                (symbol, ad, ed, str(row.get("type") or ""),
                 _to_float(row.get("net_profit_min")),
                 _to_float(row.get("net_profit_max")),
                 _to_float(row.get("last_parent_net")), _row_json(row)))
            n += 1
    return n


def _upsert_express(q_start: str, q_end: str) -> int:
    try:
        df = _call("express", start_date=q_start, end_date=q_end,
                   fields="ts_code,ann_date,end_date,revenue,net_profit")
    except Exception as exc:  # noqa: BLE001
        log.warning("express %s-%s 失败：%s", q_start, q_end, exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            ed = _to_date(row.get("end_date"))
            if not ed:
                continue
            cur.execute(
                """INSERT INTO express
                   (market, symbol, ann_date, end_date, revenue, net_profit, data)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, end_date) DO UPDATE SET
                     ann_date=EXCLUDED.ann_date, revenue=EXCLUDED.revenue,
                     net_profit=EXCLUDED.net_profit, data=EXCLUDED.data""",
                (symbol, _to_date(row.get("ann_date")), ed,
                 _to_float(row.get("revenue")), _to_float(row.get("net_profit")),
                 _row_json(row)))
            n += 1
    return n


# ---------------------------------------------------------------- 批量入口

def backfill_daily_basic(from_date: str = "") -> None:
    """每日指标，近10年。"""
    start = _to_date(from_date) or TEN_YEARS_AGO
    days = _trade_days(start, date.today())
    log.info("daily_basic 待抓取 %d 个交易日（%s 起）", len(days), start)
    t0 = time.time()
    total = 0
    for i, d in enumerate(days, 1):
        total += _upsert_daily_basic(d)
        if i % 100 == 0:
            log.info("daily_basic 进度 %d/%d，累计 %d 行，%.1fs",
                     i, len(days), total, time.time() - t0)
    log.info("daily_basic 完成：%d 个交易日，%d 行，%.1fs",
             len(days), total, time.time() - t0)


def backfill_moneyflow_suspend(from_date: str = "") -> None:
    """资金流向 + 停复牌，近2年。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("moneyflow/suspend 待抓取 %d 个交易日（%s 起）", len(days), start)
    t0 = time.time()
    tm = ts = 0
    for i, d in enumerate(days, 1):
        tm += _upsert_moneyflow(d)
        ts += _upsert_suspend(d)
        if i % 100 == 0:
            log.info("资金流/停复牌 进度 %d/%d，%.1fs",
                     i, len(days), time.time() - t0)
    log.info("资金流/停复牌完成：%d 个交易日，moneyflow %d 行，suspend %d 行，%.1fs",
             len(days), tm, ts, time.time() - t0)


def backfill_dividend(from_date: str = "") -> None:
    """分红送股，近2年（按公告日遍历交易日）。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("dividend 待抓取 %d 个公告日", len(days))
    t0 = time.time()
    total = 0
    for i, d in enumerate(days, 1):
        total += _upsert_dividend(d)
        if i % 100 == 0:
            log.info("dividend 进度 %d/%d，累计 %d 行，%.1fs",
                     i, len(days), total, time.time() - t0)
    log.info("dividend 完成：%d 行，%.1fs", total, time.time() - t0)


def backfill_forecast_express(from_date: str = "") -> None:
    """业绩预告 + 快报，近2年（按季度）。"""
    start = _to_date(from_date) or _cutoff()
    qs = _quarters(start, date.today())
    log.info("forecast/express 待抓取 %d 个季度", len(qs))
    t0 = time.time()
    tf = te = 0
    for qs_, qe in qs:
        tf += _upsert_forecast(qs_, qe)
        te += _upsert_express(qs_, qe)
    log.info("forecast/express 完成：forecast %d 行，express %d 行，%.1fs",
             tf, te, time.time() - t0)
