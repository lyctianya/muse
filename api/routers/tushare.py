"""Tushare 增量数据：每日指标、分红送股、业绩预告/快报、资金流向、停复牌。"""
from fastapi import APIRouter, Query

from ..deps import _conn

router = APIRouter()


@router.get("/api/daily-basic")
def get_daily_basic(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    limit: int = Query(default=250, le=3000, description="最近 N 个交易日"),
):
    """每日指标：PE/PB/PS/股息率/市值/换手率，按日期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio,"
                " turnover_rate, total_mv, circ_mv FROM daily_basic"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date DESC LIMIT %s",
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(), "pe": r[1], "pe_ttm": r[2],
            "pb": r[3], "ps": r[4], "ps_ttm": r[5], "dv_ratio": r[6],
            "turnover_rate": r[7], "total_mv": r[8], "circ_mv": r[9],
        }
        for r in rows
    ]


@router.get("/api/dividend")
def get_dividend(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """分红送股：按公告日倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ann_date, end_date, div_proc, stk_div, stk_bo_rate,"
                " cash_div, record_date, ex_date, pay_date FROM dividend"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY ann_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "ann_date": r[0].isoformat() if r[0] else None,
            "end_date": r[1].isoformat() if r[1] else None,
            "div_proc": r[2], "stk_div": r[3], "stk_bo_rate": r[4],
            "cash_div": r[5],
            "record_date": r[6].isoformat() if r[6] else None,
            "ex_date": r[7].isoformat() if r[7] else None,
            "pay_date": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


@router.get("/api/forecast")
def get_forecast(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """业绩预告：按公告日倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ann_date, end_date, ptype, net_profit_min,"
                " net_profit_max, last_parent_net FROM forecast"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY ann_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "ann_date": r[0].isoformat() if r[0] else None,
            "end_date": r[1].isoformat() if r[1] else None,
            "ptype": r[2], "net_profit_min": r[3],
            "net_profit_max": r[4], "last_parent_net": r[5],
        }
        for r in rows
    ]


@router.get("/api/express")
def get_express(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """业绩快报：按报告期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ann_date, end_date, revenue, net_profit FROM express"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY end_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "ann_date": r[0].isoformat() if r[0] else None,
            "end_date": r[1].isoformat() if r[1] else None,
            "revenue": r[2], "net_profit": r[3],
        }
        for r in rows
    ]


@router.get("/api/moneyflow")
def get_moneyflow(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    limit: int = Query(default=60, le=500, description="最近 N 个交易日"),
):
    """个股资金流向：按日期倒序，金额单位万元。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, buy_sm_amount, sell_sm_amount,"
                " buy_md_amount, sell_md_amount, buy_lg_amount, sell_lg_amount,"
                " buy_elg_amount, sell_elg_amount, net_mf_amount FROM moneyflow"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date DESC LIMIT %s",
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "trade_date": r[0].isoformat(),
            "buy_sm_amount": r[1], "sell_sm_amount": r[2],
            "buy_md_amount": r[3], "sell_md_amount": r[4],
            "buy_lg_amount": r[5], "sell_lg_amount": r[6],
            "buy_elg_amount": r[7], "sell_elg_amount": r[8],
            "net_mf_amount": r[9],
        }
        for r in rows
    ]


@router.get("/api/suspend")
def get_suspend(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """停复牌记录：按停牌日倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT suspend_date, resume_date, suspend_reason FROM suspend"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY suspend_date DESC LIMIT 50",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "suspend_date": r[0].isoformat(),
            "resume_date": r[1].isoformat() if r[1] else None,
            "suspend_reason": r[2],
        }
        for r in rows
    ]
