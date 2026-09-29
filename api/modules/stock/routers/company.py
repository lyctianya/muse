"""公司基本信息。"""
from fastapi import APIRouter, Query

from api.platform.deps import _conn

router = APIRouter()


@router.get("/company")
def get_company(
    market: str = Query(default="cn", description="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """上市公司基本信息：行业/PE/PB/市值等。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, industry, pe, pb, market_cap, circulating_cap,"
                " total_shares, circulating_shares, list_date, data, updated_at"
                " FROM company_info WHERE market = %s AND symbol = %s",
                (market, symbol),
            )
            r = cur.fetchone()
    if not r:
        return {"symbol": symbol, "found": False}
    return {
        "symbol": symbol, "found": True,
        "name": r[0], "industry": r[1], "pe": r[2], "pb": r[3],
        "market_cap": r[4], "circulating_cap": r[5],
        "total_shares": r[6], "circulating_shares": r[7],
        "list_date": r[8].isoformat() if r[8] else None,
        "data": r[9], "updated_at": r[10].isoformat() if r[10] else None,
    }
