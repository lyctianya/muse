"""Tushare Pro 5000积分档全量接口抓取（A股）。

15 张表：
- fina_mainbz    主营业务构成（官方，替代东财爬虫）  per-stock
- company_detail 上市公司详细信息                    批量
- namechange     股票曾用名                          批量
- top_list       龙虎榜                              按交易日
- top_inst       龙虎榜机构明细                      按交易日
- index_daily    指数日线（上证/深证/创业板等）      按指数
- moneyflow_hsgt 沪深港通资金流向                    按交易日
- hsgt_top10     沪深股通十大成交股                  按交易日
- disclosure_date 财报披露计划                      按公告日
- margin         融资融券汇总（市场级）              按交易日
- margin_detail  个股两融明细                        按交易日
- stk_limit      每日涨跌停                          按交易日（近2年）
- fina_audit     财务审计意见                        per-stock
- new_share      IPO新股                             按日期区间
- managers       上市公司管理层                      per-stock

幂等 upsert。市场级/按日表用交易日循环；per-stock 表逐只拉取。
"""
import logging
import time
from datetime import date

import pandas as pd

from fetcher import db
from fetcher.sources.tushare_fundamentals import (
    _call, _cutoff, _plain, _to_date, _to_float, _row_json,
    _ts_code,
)
from fetcher.sources.tushare_extra import _trade_days

log = logging.getLogger(__name__)

TEN_YEARS_AGO = date.today().replace(year=date.today().year - 10)

# 主要指数
INDICES = [
    "000001.SH",  # 上证综指
    "000300.SH",  # 沪深300
    "000905.SH",  # 中证500
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "000688.SH",  # 科创50
]


def _symbols_cn() -> list:
    """A股现役代码列表（6位）。"""
    pool = db.get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT symbol FROM symbols WHERE market='cn' AND active")
        return [r[0] for r in cur.fetchall()]


# ---------------------------------------------------------------- 主营业务构成

def backfill_mainbz() -> None:
    """fina_mainbz：逐只拉取近2年。约 5500 次调用。"""
    symbols = _symbols_cn()
    log.info("fina_mainbz 待抓取 %d 只", len(symbols))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, symbol in enumerate(symbols, 1):
        try:
            df = _call("fina_mainbz", ts_code=_ts_code(symbol),
                       fields="ts_code,end_date,bz_item,bz_sales,bz_profit,"
                              "bz_cost,curr_type,update_flag")
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] fina_mainbz 失败：%s", symbol, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                ed = _to_date(row.get("end_date"))
                if not ed or ed < _cutoff():
                    continue
                item = str(row.get("bz_item") or "").strip()
                if not item:
                    continue
                cur.execute(
                    """INSERT INTO fina_mainbz
                       (market, symbol, end_date, bz_item, bz_sales, bz_profit,
                        bz_cost, curr_type, update_flag)
                       VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (market, symbol, end_date, bz_item)
                       DO UPDATE SET bz_sales=EXCLUDED.bz_sales,
                         bz_profit=EXCLUDED.bz_profit,
                         bz_cost=EXCLUDED.bz_cost,
                         update_flag=EXCLUDED.update_flag""",
                    (symbol, ed, item,
                     _to_float(row.get("bz_sales")),
                     _to_float(row.get("bz_profit")),
                     _to_float(row.get("bz_cost")),
                     str(row.get("curr_type") or ""),
                     str(row.get("update_flag") or "")))
                total += 1
        if i % 200 == 0:
            log.info("fina_mainbz 进度 %d/%d，累计 %d 行，%.1fs",
                     i, len(symbols), total, time.time() - t0)
    log.info("fina_mainbz 完成：%d 行，%.1fs", total, time.time() - t0)


# ---------------------------------------------------------------- 公司详细信息

def backfill_company_detail() -> None:
    """stock_company：一次性全市场。"""
    try:
        df = _call("stock_company",
                   fields="ts_code,exchange,chairman,manager,secretary,"
                          "reg_capital,setup_date,province,city,introduction,"
                          "website,email,office,employees,main_business,"
                          "business_scope")
    except Exception as exc:  # noqa: BLE001
        log.warning("stock_company 失败：%s", exc)
        return
    if df is None or df.empty:
        return
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            emp = _to_float(row.get("employees"))
            cur.execute(
                """INSERT INTO company_detail
                   (market, symbol, exchange, chairman, manager, secretary,
                    reg_capital, setup_date, province, city, introduction,
                    website, email, office, employees, main_business,
                    business_scope)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol) DO UPDATE SET
                     chairman=EXCLUDED.chairman, manager=EXCLUDED.manager,
                     secretary=EXCLUDED.secretary,
                     reg_capital=EXCLUDED.reg_capital,
                     setup_date=EXCLUDED.setup_date,
                     province=EXCLUDED.province, city=EXCLUDED.city,
                     introduction=EXCLUDED.introduction,
                     website=EXCLUDED.website, email=EXCLUDED.email,
                     office=EXCLUDED.office, employees=EXCLUDED.employees,
                     main_business=EXCLUDED.main_business,
                     business_scope=EXCLUDED.business_scope""",
                (symbol, str(row.get("exchange") or ""),
                 str(row.get("chairman") or ""), str(row.get("manager") or ""),
                 str(row.get("secretary") or ""),
                 _to_float(row.get("reg_capital")),
                 _to_date(row.get("setup_date")),
                 str(row.get("province") or ""), str(row.get("city") or ""),
                 str(row.get("introduction") or ""),
                 str(row.get("website") or ""), str(row.get("email") or ""),
                 str(row.get("office") or ""),
                 int(emp) if emp else None,
                 str(row.get("main_business") or ""),
                 str(row.get("business_scope") or "")))
            n += 1
    log.info("company_detail 完成：%d 只", n)


# ---------------------------------------------------------------- 曾用名

def backfill_namechange() -> None:
    """namechange：一次性全市场。"""
    try:
        df = _call("namechange",
                   fields="ts_code,name,start_date,end_date,ann_date")
    except Exception as exc:  # noqa: BLE001
        log.warning("namechange 失败：%s", exc)
        return
    if df is None or df.empty:
        return
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            sd = _to_date(row.get("start_date"))
            if not sd:
                continue
            cur.execute(
                """INSERT INTO namechange (market, symbol, start_date, end_date,
                                           old_name)
                   VALUES ('cn', %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, start_date) DO UPDATE SET
                     end_date=EXCLUDED.end_date, old_name=EXCLUDED.old_name""",
                (symbol, sd, _to_date(row.get("end_date")),
                 str(row.get("name") or "")))
            n += 1
    log.info("namechange 完成：%d 行", n)


# ---------------------------------------------------------------- 龙虎榜

def _upsert_top_list(trade_date: str) -> int:
    try:
        df = _call("top_list", trade_date=trade_date,
                   fields="ts_code,trade_date,name,close,pct_change,"
                          "turnover_rate,amount,l_sell,l_buy,l_amount,"
                          "net_amount,net_rate,amount_rate,float_values,reason")
    except Exception as exc:  # noqa: BLE001
        log.warning("top_list %s 失败：%s", trade_date, exc)
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
                """INSERT INTO top_list
                   (market, symbol, trade_date, name, close, pct_change,
                    turnover_rate, amount, l_sell, l_buy, l_amount,
                    net_amount, net_rate, amount_rate, float_values, reason)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, trade_date) DO UPDATE SET
                     close=EXCLUDED.close, pct_change=EXCLUDED.pct_change,
                     net_amount=EXCLUDED.net_amount,
                     reason=EXCLUDED.reason""",
                (symbol, td, str(row.get("name") or ""),
                 _to_float(row.get("close")), _to_float(row.get("pct_change")),
                 _to_float(row.get("turnover_rate")),
                 _to_float(row.get("amount")), _to_float(row.get("l_sell")),
                 _to_float(row.get("l_buy")), _to_float(row.get("l_amount")),
                 _to_float(row.get("net_amount")),
                 _to_float(row.get("net_rate")),
                 _to_float(row.get("amount_rate")),
                 _to_float(row.get("float_values")),
                 str(row.get("reason") or "")))
            n += 1
    return n


def _upsert_top_inst(trade_date: str) -> int:
    try:
        df = _call("top_inst", trade_date=trade_date,
                   fields="ts_code,trade_date,side,exalter,buy,buy_rate,"
                          "sell,sell_rate,net_buy")
    except Exception as exc:  # noqa: BLE001
        log.warning("top_inst %s 失败：%s", trade_date, exc)
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
            side = _to_float(row.get("side"))
            exalter = str(row.get("exalter") or "").strip()
            if not exalter:
                continue
            cur.execute(
                """INSERT INTO top_inst
                   (market, symbol, trade_date, side, exalter, buy, buy_rate,
                    sell, sell_rate, net_buy)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, trade_date, side, exalter)
                   DO UPDATE SET buy=EXCLUDED.buy, sell=EXCLUDED.sell,
                     net_buy=EXCLUDED.net_buy""",
                (symbol, td, int(side) if side is not None else 0, exalter,
                 _to_float(row.get("buy")), _to_float(row.get("buy_rate")),
                 _to_float(row.get("sell")), _to_float(row.get("sell_rate")),
                 _to_float(row.get("net_buy"))))
            n += 1
    return n


def backfill_top_list(from_date: str = "") -> None:
    """龙虎榜 + 机构明细：近2年按交易日。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("top_list/top_inst 待抓取 %d 个交易日", len(days))
    t0 = time.time()
    tl = ti = 0
    for i, d in enumerate(days, 1):
        tl += _upsert_top_list(d)
        ti += _upsert_top_inst(d)
        if i % 100 == 0:
            log.info("龙虎榜进度 %d/%d，%.1fs", i, len(days), time.time() - t0)
    log.info("龙虎榜完成：top_list %d 行，top_inst %d 行，%.1fs",
             tl, ti, time.time() - t0)


# ---------------------------------------------------------------- 指数日线

def backfill_index_daily(from_date: str = "") -> None:
    """主要指数日线：近10年。"""
    start = _to_date(from_date) or TEN_YEARS_AGO
    s_str = start.strftime("%Y%m%d")
    e_str = date.today().strftime("%Y%m%d")
    log.info("index_daily 待抓取 %d 个指数（%s 起）", len(INDICES), start)
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for ts_code in INDICES:
        try:
            df = _call("index_daily", ts_code=ts_code,
                       start_date=s_str, end_date=e_str,
                       fields="ts_code,trade_date,open,high,low,close,"
                              "pre_close,change,pct_chg,vol,amount")
        except Exception as exc:  # noqa: BLE001
            log.warning("index_daily %s 失败：%s", ts_code, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                td = _to_date(row.get("trade_date"))
                if not td:
                    continue
                cur.execute(
                    """INSERT INTO index_daily
                       (market, ts_code, trade_date, open, high, low, close,
                        pre_close, change, pct_change, vol, amount)
                       VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (market, ts_code, trade_date) DO UPDATE SET
                         close=EXCLUDED.close,
                         pct_change=EXCLUDED.pct_change,
                         amount=EXCLUDED.amount""",
                    (ts_code, td,
                     _to_float(row.get("open")), _to_float(row.get("high")),
                     _to_float(row.get("low")), _to_float(row.get("close")),
                     _to_float(row.get("pre_close")),
                     _to_float(row.get("change")),
                     _to_float(row.get("pct_chg")),
                     _to_float(row.get("vol")), _to_float(row.get("amount"))))
                total += 1
    log.info("index_daily 完成：%d 行，%.1fs", total, time.time() - t0)


# ---------------------------------------------------------------- 沪深港通

def backfill_moneyflow_hsgt(from_date: str = "") -> None:
    """沪深港通资金流向：近2年按交易日。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("moneyflow_hsgt 待抓取 %d 个交易日", len(days))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, d in enumerate(days, 1):
        try:
            df = _call("moneyflow_hsgt", trade_date=d,
                       fields="trade_date,ggt_ss,ggt_sz,hgt,sgt,north_money,"
                              "south_money")
        except Exception as exc:  # noqa: BLE001
            log.warning("moneyflow_hsgt %s 失败：%s", d, exc)
            continue
        if df is None or df.empty:
            continue
        td = _to_date(d)
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute(
                    """INSERT INTO moneyflow_hsgt
                       (market, trade_date, ggt_ss, ggt_sz, hgt, sgt,
                        north_money, south_money)
                       VALUES ('cn', %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (market, trade_date) DO UPDATE SET
                         ggt_ss=EXCLUDED.ggt_ss, ggt_sz=EXCLUDED.ggt_sz,
                         hgt=EXCLUDED.hgt, sgt=EXCLUDED.sgt,
                         north_money=EXCLUDED.north_money,
                         south_money=EXCLUDED.south_money""",
                    (td, _to_float(row.get("ggt_ss")),
                     _to_float(row.get("ggt_sz")), _to_float(row.get("hgt")),
                     _to_float(row.get("sgt")),
                     _to_float(row.get("north_money")),
                     _to_float(row.get("south_money"))))
                total += 1
        if i % 100 == 0:
            log.info("hsgt资金流进度 %d/%d，%.1fs", i, len(days), time.time() - t0)
    log.info("moneyflow_hsgt 完成：%d 行，%.1fs", total, time.time() - t0)


def backfill_hsgt_top10(from_date: str = "") -> None:
    """沪深股通十大成交股：近2年按交易日。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("hsgt_top10 待抓取 %d 个交易日", len(days))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, d in enumerate(days, 1):
        for gtype in ("沪", "深"):
            try:
                df = _call("hsgt_top10", trade_date=d, market_type=gtype,
                           fields="ts_code,trade_date,buy_amount,sell_amount,"
                                  "net_amount")
            except Exception as exc:  # noqa: BLE001
                log.warning("hsgt_top10 %s %s 失败：%s", d, gtype, exc)
                continue
            if df is None or df.empty:
                continue
            td = _to_date(d)
            with pool.connection() as conn, conn.cursor() as cur:
                for rank, (_, row) in enumerate(df.iterrows(), 1):
                    symbol = _plain(str(row["ts_code"]))
                    if len(symbol) != 6:
                        continue
                    cur.execute(
                        """INSERT INTO hsgt_top10
                           (market, symbol, trade_date, gtype, rank,
                            buy_amount, sell_amount, net_amount)
                           VALUES ('cn', %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (market, symbol, trade_date, gtype)
                           DO UPDATE SET buy_amount=EXCLUDED.buy_amount,
                             sell_amount=EXCLUDED.sell_amount,
                             net_amount=EXCLUDED.net_amount""",
                        (symbol, td, gtype, rank,
                         _to_float(row.get("buy_amount")),
                         _to_float(row.get("sell_amount")),
                         _to_float(row.get("net_amount"))))
                    total += 1
        if i % 100 == 0:
            log.info("hsgt_top10 进度 %d/%d，%.1fs", i, len(days), time.time() - t0)
    log.info("hsgt_top10 完成：%d 行，%.1fs", total, time.time() - t0)


# ---------------------------------------------------------------- 财报披露计划

def backfill_disclosure_date() -> None:
    """disclosure_date：按公告日遍历近2年交易日。"""
    days = _trade_days(_cutoff(), date.today())
    log.info("disclosure_date 待抓取 %d 个公告日", len(days))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, d in enumerate(days, 1):
        try:
            df = _call("disclosure_date", ann_date=d,
                       fields="ts_code,ann_date,end_date,pre_date,actual_date")
        except Exception as exc:  # noqa: BLE001
            log.warning("disclosure_date %s 失败：%s", d, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                symbol = _plain(str(row["ts_code"]))
                if len(symbol) != 6:
                    continue
                ed = _to_date(row.get("end_date"))
                if not ed:
                    continue
                cur.execute(
                    """INSERT INTO disclosure_date
                       (market, symbol, end_date, ann_date, pre_date,
                        actual_date)
                       VALUES ('cn', %s, %s, %s, %s, %s)
                       ON CONFLICT (market, symbol, end_date) DO UPDATE SET
                         ann_date=EXCLUDED.ann_date,
                         pre_date=EXCLUDED.pre_date,
                         actual_date=EXCLUDED.actual_date""",
                    (symbol, ed, _to_date(row.get("ann_date")),
                     _to_date(row.get("pre_date")),
                     _to_date(row.get("actual_date"))))
                total += 1
        if i % 100 == 0:
            log.info("disclosure_date 进度 %d/%d，%.1fs",
                     i, len(days), time.time() - t0)
    log.info("disclosure_date 完成：%d 行，%.1fs", total, time.time() - t0)


# ---------------------------------------------------------------- 融资融券

def backfill_margin(from_date: str = "") -> None:
    """margin 汇总 + margin_detail 明细：近2年按交易日。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("margin 待抓取 %d 个交易日", len(days))
    t0 = time.time()
    m_sum = m_det = 0
    pool = db.get_pool()
    for i, d in enumerate(days, 1):
        td = _to_date(d)
        # 汇总（沪深）
        try:
            df = _call("margin", trade_date=d,
                       fields="trade_date,exchange_id,rzye,rqye,rzrqye,rqyl")
            if df is not None and not df.empty:
                with pool.connection() as conn, conn.cursor() as cur:
                    for _, row in df.iterrows():
                        cur.execute(
                            """INSERT INTO margin
                               (market, trade_date, exchange_id, rzye, rqye,
                                rzrqye, rqyl)
                               VALUES ('cn', %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (market, trade_date, exchange_id)
                               DO UPDATE SET rzye=EXCLUDED.rzye,
                                 rqye=EXCLUDED.rqye,
                                 rzrqye=EXCLUDED.rzrqye,
                                 rqyl=EXCLUDED.rqyl""",
                            (td, str(row.get("exchange_id") or ""),
                             _to_float(row.get("rzye")),
                             _to_float(row.get("rqye")),
                             _to_float(row.get("rzrqye")),
                             _to_float(row.get("rqyl"))))
                        m_sum += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("margin %s 失败：%s", d, exc)
        # 明细
        try:
            df = _call("margin_detail", trade_date=d,
                       fields="ts_code,trade_date,rzye,rqye,rzrqye,rqyl")
            if df is not None and not df.empty:
                with pool.connection() as conn, conn.cursor() as cur:
                    for _, row in df.iterrows():
                        symbol = _plain(str(row["ts_code"]))
                        if len(symbol) != 6:
                            continue
                        cur.execute(
                            """INSERT INTO margin_detail
                               (market, symbol, trade_date, rzye, rqye,
                                rzrqye, rqyl)
                               VALUES ('cn', %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (market, symbol, trade_date)
                               DO UPDATE SET rzye=EXCLUDED.rzye,
                                 rqye=EXCLUDED.rqye,
                                 rzrqye=EXCLUDED.rzrqye,
                                 rqyl=EXCLUDED.rqyl""",
                            (symbol, td, _to_float(row.get("rzye")),
                             _to_float(row.get("rqye")),
                             _to_float(row.get("rzrqye")),
                             _to_float(row.get("rqyl"))))
                        m_det += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("margin_detail %s 失败：%s", d, exc)
        if i % 100 == 0:
            log.info("两融进度 %d/%d，%.1fs", i, len(days), time.time() - t0)
    log.info("两融完成：margin %d 行，margin_detail %d 行，%.1fs",
             m_sum, m_det, time.time() - t0)


# ---------------------------------------------------------------- 涨跌停

def backfill_stk_limit(from_date: str = "") -> None:
    """stk_limit：近2年按交易日（约 500 天 × 5000 只 = 250 万行）。"""
    start = _to_date(from_date) or _cutoff()
    days = _trade_days(start, date.today())
    log.info("stk_limit 待抓取 %d 个交易日", len(days))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, d in enumerate(days, 1):
        try:
            df = _call("stk_limit", trade_date=d,
                       fields="ts_code,trade_date,pre_close,up_limit,"
                              "down_limit")
        except Exception as exc:  # noqa: BLE001
            log.warning("stk_limit %s 失败：%s", d, exc)
            continue
        if df is None or df.empty:
            continue
        td = _to_date(d)
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                symbol = _plain(str(row["ts_code"]))
                if len(symbol) != 6:
                    continue
                cur.execute(
                    """INSERT INTO stk_limit
                       (market, symbol, trade_date, pre_close, up_limit,
                        down_limit)
                       VALUES ('cn', %s, %s, %s, %s, %s)
                       ON CONFLICT (market, symbol, trade_date) DO UPDATE SET
                         pre_close=EXCLUDED.pre_close,
                         up_limit=EXCLUDED.up_limit,
                         down_limit=EXCLUDED.down_limit""",
                    (symbol, td, _to_float(row.get("pre_close")),
                     _to_float(row.get("up_limit")),
                     _to_float(row.get("down_limit"))))
                total += 1
        if i % 50 == 0:
            log.info("stk_limit 进度 %d/%d，累计 %d 行，%.1fs",
                     i, len(days), total, time.time() - t0)
    log.info("stk_limit 完成：%d 行，%.1fs", total, time.time() - t0)


# ---------------------------------------------------------------- 审计意见（per-stock）

def backfill_fina_audit() -> None:
    """fina_audit：逐只拉取近2年。"""
    symbols = _symbols_cn()
    log.info("fina_audit 待抓取 %d 只", len(symbols))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, symbol in enumerate(symbols, 1):
        try:
            df = _call("fina_audit", ts_code=_ts_code(symbol),
                       fields="ts_code,end_date,ann_date,audit_result,"
                              "audit_fees,audit_agency")
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] fina_audit 失败：%s", symbol, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                ed = _to_date(row.get("end_date"))
                if not ed or ed < _cutoff():
                    continue
                cur.execute(
                    """INSERT INTO fina_audit
                       (market, symbol, end_date, ann_date, audit_result,
                        audit_fees, audit_agency, data)
                       VALUES ('cn', %s, %s, %s, %s, %s, %s, %s::jsonb)
                       ON CONFLICT (market, symbol, end_date) DO UPDATE SET
                         audit_result=EXCLUDED.audit_result,
                         audit_agency=EXCLUDED.audit_agency,
                         data=EXCLUDED.data""",
                    (symbol, ed, _to_date(row.get("ann_date")),
                     str(row.get("audit_result") or ""),
                     _to_float(row.get("audit_fees")),
                     str(row.get("audit_agency") or ""), _row_json(row)))
                total += 1
        if i % 500 == 0:
            log.info("fina_audit 进度 %d/%d，%.1fs", i, len(symbols),
                     time.time() - t0)
    log.info("fina_audit 完成：%d 行，%.1fs", total, time.time() - t0)


# ---------------------------------------------------------------- IPO 新股

def backfill_new_share() -> None:
    """new_share：近2年一次性。"""
    try:
        df = _call("new_share",
                   start_date=_cutoff().strftime("%Y%m%d"),
                   end_date=date.today().strftime("%Y%m%d"),
                   fields="ts_code,sub_code,name,price,total_amount,"
                          "online_amount,issue_date,list_date")
    except Exception as exc:  # noqa: BLE001
        log.warning("new_share 失败：%s", exc)
        return
    if df is None or df.empty:
        return
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            cur.execute(
                """INSERT INTO new_share
                   (market, symbol, name, price, total_amount, online_amount,
                    issue_date, list_date, data)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol) DO UPDATE SET
                     name=EXCLUDED.name, price=EXCLUDED.price,
                     list_date=EXCLUDED.list_date, data=EXCLUDED.data""",
                (symbol, str(row.get("name") or ""),
                 _to_float(row.get("price")),
                 _to_float(row.get("total_amount")),
                 _to_float(row.get("online_amount")),
                 _to_date(row.get("issue_date")),
                 _to_date(row.get("list_date")), _row_json(row)))
            n += 1
    log.info("new_share 完成：%d 行", n)


# ---------------------------------------------------------------- 管理层（per-stock）

def backfill_managers() -> None:
    """stk_managers：逐只拉取。约 5500 次调用。"""
    symbols = _symbols_cn()
    log.info("managers 待抓取 %d 只", len(symbols))
    t0 = time.time()
    total = 0
    pool = db.get_pool()
    for i, symbol in enumerate(symbols, 1):
        try:
            df = _call("stk_managers", ts_code=_ts_code(symbol),
                       fields="ts_code,ann_date,name,gender,lev,title,edu,"
                              "national,birthday,begin_date,end_date,resume")
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] stk_managers 失败：%s", symbol, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                name = str(row.get("name") or "").strip()
                ad = _to_date(row.get("ann_date"))
                if not name or not ad:
                    continue
                cur.execute(
                    """INSERT INTO managers
                       (market, symbol, name, gender, lev, title, edu,
                        national, birthday, begin_date, end_date, resume,
                        ann_date)
                       VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               %s, %s)
                       ON CONFLICT (market, symbol, name, ann_date)
                       DO UPDATE SET title=EXCLUDED.title,
                         end_date=EXCLUDED.end_date,
                         resume=EXCLUDED.resume""",
                    (symbol, name, str(row.get("gender") or ""),
                     str(row.get("lev") or ""), str(row.get("title") or ""),
                     str(row.get("edu") or ""),
                     str(row.get("national") or ""),
                     str(row.get("birthday") or ""),
                     _to_date(row.get("begin_date")),
                     _to_date(row.get("end_date")),
                     str(row.get("resume") or "")[:2000], ad))
                total += 1
        if i % 200 == 0:
            log.info("managers 进度 %d/%d，累计 %d 行，%.1fs",
                     i, len(symbols), total, time.time() - t0)
    log.info("managers 完成：%d 行，%.1fs", total, time.time() - t0)
