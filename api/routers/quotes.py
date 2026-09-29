"""行情：股票搜索、日线、周文件列表。"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from ..deps import _conn

router = APIRouter()


@router.get("/api/symbols")
def search_symbols(
    market: Optional[str] = Query(default=None, description="cn/hk/us，不传则全市场"),
    q: str = Query(default="", description="代码或名称关键字"),
    limit: int = Query(default=50, le=200),
):
    """搜索股票：按代码/名称模糊匹配，只返回现役（active）股票。"""
    sql = (
        "SELECT s.market, s.symbol,"
        " COALESCE(NULLIF(c.name, ''), NULLIF(s.name, s.symbol), s.name),"
        " s.currency"
        " FROM symbols s"
        " LEFT JOIN company_info c ON c.market = s.market AND c.symbol = s.symbol"
        " WHERE s.active = TRUE"
    )
    params: list = []
    if market:
        sql += " AND s.market = %s"
        params.append(market)
    if q:
        sql += (
            " AND (s.symbol ILIKE %s OR s.name ILIKE %s"
            " OR COALESCE(c.name, '') ILIKE %s)"
        )
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY s.market, s.symbol LIMIT %s"
    params.append(limit)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [
        {"market": r[0], "symbol": r[1], "name": r[2], "currency": r[3]}
        for r in rows
    ]


@router.get("/api/bars")
def get_bars(
    market: str = Query(description="cn/hk/us"),
    symbol: str = Query(description="股票代码，如 600519"),
    from_: date = Query(alias="from", description="起始日期 YYYY-MM-DD"),
    to: date = Query(alias="to", description="结束日期 YYYY-MM-DD"),
):
    """取某只股票指定区间的日线（前复权），按日期升序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, open, high, low, close, volume, amount,"
                " pct_change, currency FROM daily_bars"
                " WHERE market = %s AND symbol = %s"
                " AND trade_date BETWEEN %s AND %s"
                " ORDER BY trade_date",
                (market, symbol, from_, to),
            )
            rows = cur.fetchall()
    return [
        {
            "date": r[0].isoformat(),
            "open": r[1], "high": r[2], "low": r[3], "close": r[4],
            "volume": r[5], "amount": r[6], "pct_change": r[7],
            "currency": r[8],
        }
        for r in rows
    ]


@router.get("/api/weeks")
def list_weeks():
    """可下载的周文件列表。

    占位实现：待周导出任务产出 manifest 并接入 GitHub Releases 后，
    这里改为读取 manifest / Release 列表返回真实数据。
    """
    return {"weeks": []}
