"""自选股（单用户，user_id 固定为 'default'）。"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..deps import _conn

router = APIRouter()

USER = "default"


class WatchBody(BaseModel):
    market: str = "cn"
    symbol: str
    group_name: Optional[str] = "默认分组"
    note: Optional[str] = ""


def _has_table(cur, name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (name,),
    )
    return cur.fetchone() is not None


@router.get("/api/watchlist")
def list_watchlist():
    """自选股列表：按分组/加入时间排序，附最新行情与估值。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            if not _has_table(cur, "watchlist"):
                return []
            has_basic = _has_table(cur, "daily_basic")
            basic_join = (
                "LEFT JOIN LATERAL ("
                " SELECT total_mv, pe_ttm FROM daily_basic"
                " WHERE market = w.market AND symbol = w.symbol"
                " ORDER BY trade_date DESC LIMIT 1) d ON TRUE"
                if has_basic else
                "LEFT JOIN (SELECT NULL::numeric AS total_mv,"
                " NULL::numeric AS pe_ttm) d ON TRUE"
            )
            cur.execute(
                "SELECT w.market, w.symbol,"
                " COALESCE(NULLIF(c.name, ''), NULLIF(s.name, s.symbol), s.name),"
                " w.group_name, w.note,"
                " w.added_at, b.close, b.pct_change, d.total_mv, d.pe_ttm"
                " FROM watchlist w"
                " LEFT JOIN symbols s"
                "  ON s.market = w.market AND s.symbol = w.symbol"
                " LEFT JOIN company_info c"
                "  ON c.market = w.market AND c.symbol = w.symbol"
                " LEFT JOIN LATERAL ("
                "  SELECT close, pct_change FROM daily_bars"
                "  WHERE market = w.market AND symbol = w.symbol"
                "  ORDER BY trade_date DESC LIMIT 1) b ON TRUE "
                + basic_join +
                " WHERE w.user_id = %s"
                " ORDER BY w.group_name, w.added_at",
                (USER,),
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        mv = r[8]
        out.append({
            "market": r[0], "symbol": r[1], "name": r[2],
            "group_name": r[3] or "默认分组", "note": r[4] or "",
            "added_at": r[5].isoformat() if r[5] else None,
            "close": float(r[6]) if r[6] is not None else None,
            "pct_change": float(r[7]) if r[7] is not None else None,
            "total_mv_yi": round(float(mv) / 1e8, 2) if mv else None,
            "pe_ttm": float(r[9]) if r[9] is not None else None,
        })
    return out


def _ensure_symbol(cur, market: str, symbol: str) -> None:
    cur.execute(
        "SELECT 1 FROM symbols WHERE market = %s AND symbol = %s",
        (market, symbol),
    )
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="股票不存在")


@router.post("/api/watchlist")
def add_watchlist(body: WatchBody):
    """加入自选：已存在则更新分组/备注（upsert）。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            _ensure_symbol(cur, body.market, body.symbol)
            cur.execute(
                "INSERT INTO watchlist"
                " (user_id, market, symbol, group_name, note)"
                " VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (user_id, market, symbol) DO UPDATE SET"
                " group_name = EXCLUDED.group_name,"
                " note = EXCLUDED.note",
                (USER, body.market, body.symbol,
                 body.group_name or "默认分组", body.note or ""),
            )
    return {"ok": True}


@router.delete("/api/watchlist")
def remove_watchlist(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """从自选删除。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist"
                " WHERE user_id = %s AND market = %s AND symbol = %s",
                (USER, market, symbol),
            )
    return {"ok": True}


@router.put("/api/watchlist")
def update_watchlist(body: WatchBody):
    """只更新分组/备注（不改变加入时间）。"""
    sets, params = [], []
    if body.group_name is not None:
        sets.append("group_name = %s")
        params.append(body.group_name or "默认分组")
    if body.note is not None:
        sets.append("note = %s")
        params.append(body.note)
    if not sets:
        return {"ok": True}
    params += [USER, body.market, body.symbol]
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE watchlist SET {', '.join(sets)}"
                " WHERE user_id = %s AND market = %s AND symbol = %s",
                params,
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="不在自选中")
    return {"ok": True}
