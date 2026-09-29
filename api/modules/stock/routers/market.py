"""市场概览（Dashboard）：涨跌统计、涨跌幅榜、行业分布。"""
from fastapi import APIRouter, Query

from api.platform.deps import _conn

router = APIRouter()


@router.get("/market/overview")
def market_overview(market: str = Query(description="cn/hk/us")):
    """某市场最新交易日的概览：涨跌家数、成交额、股票数。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(trade_date) FROM daily_bars WHERE market = %s",
                (market,),
            )
            latest = cur.fetchone()[0]
            if latest is None:
                return {"market": market, "found": False}
            cur.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END),
                          SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END),
                          SUM(CASE WHEN pct_change = 0 THEN 1 ELSE 0 END),
                          SUM(amount), SUM(volume)
                   FROM daily_bars WHERE market = %s AND trade_date = %s""",
                (market, latest),
            )
            total, up, down, flat, amount, volume = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM symbols WHERE market = %s AND active = TRUE",
                (market,),
            )
            listed = cur.fetchone()[0]
    return {
        "market": market, "found": True,
        "trade_date": latest.isoformat(),
        "total": total, "up": up or 0, "down": down or 0, "flat": flat or 0,
        "amount": float(amount or 0), "volume": float(volume or 0),
        "listed": listed,
    }


@router.get("/market/top")
def market_top(
    market: str = Query(description="cn/hk/us"),
    type: str = Query(default="gainers", description="gainers|losers",
                      pattern="^(gainers|losers)$"),
    limit: int = Query(default=20, le=100),
):
    """最新交易日涨幅榜 / 跌幅榜。"""
    order = "DESC" if type == "gainers" else "ASC"
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT b.symbol,
                           COALESCE(NULLIF(c.name, ''), NULLIF(s.name, s.symbol), s.name),
                           b.close, b.pct_change, b.amount
                    FROM daily_bars b
                    JOIN symbols s ON s.market = b.market AND s.symbol = b.symbol
                    LEFT JOIN company_info c
                      ON c.market = b.market AND c.symbol = b.symbol
                    WHERE b.market = %s
                      AND b.trade_date = (
                          SELECT MAX(trade_date) FROM daily_bars WHERE market = %s)
                      AND b.pct_change IS NOT NULL
                    ORDER BY b.pct_change {order} LIMIT %s""",
                (market, market, limit),
            )
            rows = cur.fetchall()
    return [
        {"symbol": r[0], "name": r[1], "close": float(r[2]),
         "pct_change": float(r[3]), "amount": float(r[4] or 0)}
        for r in rows
    ]


@router.get("/market/sectors")
def market_sectors(market: str = Query(description="cn/hk/us")):
    """行业分布（依赖 company_info，基本面回填后才有数据）。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT industry, COUNT(*)
                   FROM company_info
                   WHERE market = %s AND industry IS NOT NULL AND industry <> ''
                   GROUP BY industry ORDER BY COUNT(*) DESC""",
                (market,),
            )
            rows = cur.fetchall()
    return [{"industry": r[0], "count": r[1]} for r in rows]
