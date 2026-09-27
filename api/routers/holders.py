"""股东相关：十大股东、股权质押、股东人数、股东增减持。"""
from fastapi import APIRouter, Query

from ..deps import _conn

router = APIRouter()


@router.get("/api/holders")
def get_holders(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    type: str = Query(default="top10", description="top10|float10",
                      pattern="^(top10|float10)$"),
):
    """前十大股东 / 前十大流通股东：按报告期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT report_date, rank, holder_name, hold_shares, hold_ratio,"
                " change FROM top_holders"
                " WHERE market = %s AND symbol = %s AND holder_type = %s"
                " ORDER BY report_date DESC, rank",
                (market, symbol, type),
            )
            rows = cur.fetchall()
    return [
        {
            "report_date": r[0].isoformat(), "rank": r[1],
            "holder_name": r[2], "hold_shares": r[3],
            "hold_ratio": r[4], "change": r[5],
        }
        for r in rows
    ]


@router.get("/api/pledge")
def get_pledge(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """股权质押：按统计日期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stat_date, pledge_ratio, pledged_shares, data"
                " FROM pledge_info WHERE market = %s AND symbol = %s"
                " ORDER BY stat_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "stat_date": r[0].isoformat(), "pledge_ratio": r[1],
            "pledged_shares": r[2], "data": r[3],
        }
        for r in rows
    ]


@router.get("/api/holder-numbers")
def get_holder_numbers(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """股东人数历史序列。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT report_date, holder_count, avg_shares FROM holder_number"
                " WHERE market = %s AND symbol = %s ORDER BY report_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "report_date": r[0].isoformat(),
            "holder_count": r[1], "avg_shares": r[2],
        }
        for r in rows
    ]


@router.get("/api/holder-trades")
def get_holder_trades(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    limit: int = Query(default=100, le=500),
):
    """股东增减持记录。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT holder_name, trade_type, trade_date, shares, price,"
                " amount, ratio FROM holder_trade"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date DESC LIMIT %s",
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "holder_name": r[0], "trade_type": r[1],
            "trade_date": r[2].isoformat() if r[2] else None,
            "shares": r[3], "price": r[4], "amount": r[5], "ratio": r[6],
        }
        for r in rows
    ]
