"""Tushare 全量接口（5000积分档新增 15 张表）查询端点。"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from ..deps import _conn

router = APIRouter()


@router.get("/api/mainbz")
def get_mainbz(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """主营业务构成（官方 fina_mainbz）：按报告期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT end_date, bz_item, bz_sales, bz_profit, bz_cost,"
                " curr_type, update_flag FROM fina_mainbz"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY end_date DESC, bz_sales DESC NULLS LAST",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "end_date": r[0].isoformat(), "bz_item": r[1],
            "bz_sales": r[2], "bz_profit": r[3], "bz_cost": r[4],
            "curr_type": r[5], "update_flag": r[6],
        }
        for r in rows
    ]


@router.get("/api/company-detail")
def get_company_detail(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """上市公司详细信息：董事长/总经理/注册资本/主营业务等。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT exchange, chairman, manager, secretary, reg_capital,"
                " setup_date, province, city, introduction, website, email,"
                " office, employees, main_business, business_scope"
                " FROM company_detail WHERE market = %s AND symbol = %s",
                (market, symbol),
            )
            r = cur.fetchone()
    if not r:
        return {"symbol": symbol, "found": False}
    return {
        "symbol": symbol, "found": True,
        "exchange": r[0], "chairman": r[1], "manager": r[2],
        "secretary": r[3], "reg_capital": r[4],
        "setup_date": r[5].isoformat() if r[5] else None,
        "province": r[6], "city": r[7], "introduction": r[8],
        "website": r[9], "email": r[10], "office": r[11],
        "employees": r[12], "main_business": r[13],
        "business_scope": r[14],
    }


@router.get("/api/namechange")
def get_namechange(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """股票曾用名：按变更时间倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT start_date, end_date, old_name FROM namechange"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY start_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "start_date": r[0].isoformat(),
            "end_date": r[1].isoformat() if r[1] else None,
            "old_name": r[2],
        }
        for r in rows
    ]


@router.get("/api/top-list")
def get_top_list(
    market: str = Query(default="cn"),
    date_: Optional[date] = Query(default=None, alias="date",
                                  description="交易日 YYYY-MM-DD，默认最新"),
    limit: int = Query(default=100, le=500),
):
    """龙虎榜：按交易日倒序（默认最新交易日）。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            if date_ is None:
                cur.execute(
                    "SELECT MAX(trade_date) FROM top_list WHERE market = %s",
                    (market,),
                )
                date_ = cur.fetchone()[0]
                if date_ is None:
                    return []
            cur.execute(
                "SELECT symbol, trade_date, name, close, pct_change,"
                " turnover_rate, amount, net_amount, net_rate, reason"
                " FROM top_list WHERE market = %s AND trade_date = %s"
                " ORDER BY amount DESC NULLS LAST LIMIT %s",
                (market, date_, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "symbol": r[0], "trade_date": r[1].isoformat(), "name": r[2],
            "close": r[3], "pct_change": r[4], "turnover_rate": r[5],
            "amount": r[6], "net_amount": r[7], "net_rate": r[8],
            "reason": r[9],
        }
        for r in rows
    ]


@router.get("/api/top-inst")
def get_top_inst(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    limit: int = Query(default=100, le=500),
):
    """龙虎榜机构明细：按交易日倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, side, exalter, buy, buy_rate, sell,"
                " sell_rate, net_buy FROM top_inst"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date DESC, net_buy DESC NULLS LAST LIMIT %s",
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(),
            "side": "买方" if r[1] == 0 else "卖方",
            "exalter": r[2], "buy": r[3], "buy_rate": r[4],
            "sell": r[5], "sell_rate": r[6], "net_buy": r[7],
        }
        for r in rows
    ]


@router.get("/api/index-daily")
def get_index_daily(
    ts_code: str = Query(default="000001.SH", description="指数代码，如 000001.SH"),
    from_: date = Query(alias="from", description="起始日期 YYYY-MM-DD"),
    to: date = Query(alias="to", description="结束日期 YYYY-MM-DD"),
):
    """指数日线：上证/沪深300/中证500/深证成指/创业板指/科创50。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, open, high, low, close, pre_close,"
                " change, pct_change, vol, amount FROM index_daily"
                " WHERE market = 'cn' AND ts_code = %s"
                " AND trade_date BETWEEN %s AND %s ORDER BY trade_date",
                (ts_code, from_, to),
            )
            rows = cur.fetchall()
    return [
        {
            "date": r[0].isoformat(), "open": r[1], "high": r[2],
            "low": r[3], "close": r[4], "pre_close": r[5],
            "change": r[6], "pct_change": r[7], "vol": r[8], "amount": r[9],
        }
        for r in rows
    ]


@router.get("/api/hsgt-flow")
def get_hsgt_flow(
    market: str = Query(default="cn"),
    limit: int = Query(default=60, le=500, description="最近 N 个交易日"),
):
    """沪深港通资金流向（市场级）：按日期倒序，金额单位亿元。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, ggt_ss, ggt_sz, hgt, sgt, north_money,"
                " south_money FROM moneyflow_hsgt"
                " WHERE market = %s ORDER BY trade_date DESC LIMIT %s",
                (market, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(), "ggt_ss": r[1], "ggt_sz": r[2],
            "hgt": r[3], "sgt": r[4],
            "north_money": r[5], "south_money": r[6],
        }
        for r in rows
    ]


@router.get("/api/hsgt-top10")
def get_hsgt_top10(
    market: str = Query(default="cn"),
    date_: Optional[date] = Query(default=None, alias="date",
                                  description="交易日，默认最新"),
):
    """沪深股通十大成交股：按净买入倒序，金额单位万元。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            if date_ is None:
                cur.execute(
                    "SELECT MAX(trade_date) FROM hsgt_top10 WHERE market = %s",
                    (market,),
                )
                date_ = cur.fetchone()[0]
                if date_ is None:
                    return []
            cur.execute(
                "SELECT symbol, gtype, rank, buy_amount, sell_amount,"
                " net_amount FROM hsgt_top10"
                " WHERE market = %s AND trade_date = %s"
                " ORDER BY gtype, rank",
                (market, date_),
            )
            rows = cur.fetchall()
    return [
        {
            "symbol": r[0], "trade_date": date_.isoformat(),
            "gtype": "沪股通" if r[1] == "沪" else "深股通",
            "rank": r[2], "buy_amount": r[3], "sell_amount": r[4],
            "net_amount": r[5],
        }
        for r in rows
    ]


@router.get("/api/disclosure")
def get_disclosure(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """财报披露计划：预约披露日 vs 实际披露日。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT end_date, ann_date, pre_date, actual_date"
                " FROM disclosure_date WHERE market = %s AND symbol = %s"
                " ORDER BY end_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "end_date": r[0].isoformat(),
            "ann_date": r[1].isoformat() if r[1] else None,
            "pre_date": r[2].isoformat() if r[2] else None,
            "actual_date": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]


@router.get("/api/margin")
def get_margin(
    market: str = Query(default="cn"),
    limit: int = Query(default=60, le=500, description="最近 N 个交易日"),
):
    """融资融券市场汇总：沪深两市余额走势，金额单位亿元。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, exchange_id, rzye, rqye, rzrqye, rqyl"
                " FROM margin WHERE market = %s"
                " ORDER BY trade_date DESC, exchange_id LIMIT %s",
                (market, limit * 2),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(), "exchange_id": r[1],
            "rzye": r[2], "rqye": r[3], "rzrqye": r[4], "rqyl": r[5],
        }
        for r in rows
    ]


@router.get("/api/margin-detail")
def get_margin_detail(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    limit: int = Query(default=60, le=500, description="最近 N 个交易日"),
):
    """个股两融明细：按日期倒序，金额单位万元。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, rzye, rqye, rzrqye, rqyl FROM margin_detail"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date DESC LIMIT %s",
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(), "rzye": r[1], "rqye": r[2],
            "rzrqye": r[3], "rqyl": r[4],
        }
        for r in rows
    ]


@router.get("/api/stk-limit")
def get_stk_limit(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    limit: int = Query(default=60, le=500, description="最近 N 个交易日"),
):
    """每日涨跌停价：按日期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, pre_close, up_limit, down_limit"
                " FROM stk_limit WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date DESC LIMIT %s",
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(), "pre_close": r[1],
            "up_limit": r[2], "down_limit": r[3],
        }
        for r in rows
    ]


@router.get("/api/fina-audit")
def get_fina_audit(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """财务审计意见：按报告期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT end_date, ann_date, audit_result, audit_fees,"
                " audit_agency FROM fina_audit"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY end_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "end_date": r[0].isoformat(),
            "ann_date": r[1].isoformat() if r[1] else None,
            "audit_result": r[2], "audit_fees": r[3],
            "audit_agency": r[4],
        }
        for r in rows
    ]


@router.get("/api/new-share")
def get_new_share(
    market: str = Query(default="cn"),
    limit: int = Query(default=100, le=500),
):
    """IPO 新股：按上市日倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol, name, price, total_amount, online_amount,"
                " issue_date, list_date FROM new_share"
                " WHERE market = %s"
                " ORDER BY list_date DESC NULLS LAST LIMIT %s",
                (market, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "symbol": r[0], "name": r[1], "price": r[2],
            "total_amount": r[3], "online_amount": r[4],
            "issue_date": r[5].isoformat() if r[5] else None,
            "list_date": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


@router.get("/api/managers")
def get_managers(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """上市公司管理层：按公告日倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, gender, lev, title, edu, national, birthday,"
                " begin_date, end_date, resume, ann_date FROM managers"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY ann_date DESC NULLS LAST, name",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "name": r[0], "gender": r[1], "lev": r[2], "title": r[3],
            "edu": r[4], "national": r[5], "birthday": r[6],
            "begin_date": r[7].isoformat() if r[7] else None,
            "end_date": r[8].isoformat() if r[8] else None,
            "resume": r[9],
            "ann_date": r[10].isoformat() if r[10] else None,
        }
        for r in rows
    ]
