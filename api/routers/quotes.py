"""行情：股票搜索、日线、周文件列表。"""
import json
import os
import re
import urllib.request
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..deps import _conn
from .auth import require_perm

router = APIRouter()

WEEK_TAG_RE = re.compile(r"^data-(\d{4}-W\d{2})$")


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
def list_weeks(_: dict = Depends(require_perm("weeks:download"))):
    """可下载的周文件列表：读 GitHub Releases 的 data-* 包（含附件直链）。

    公开仓库无需鉴权；失败时返回空列表 + note，前端照常渲染。
    """
    repo = os.environ.get("GITHUB_REPO", "") or "lyctianya/muse"
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases?per_page=100",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "stock-data-pipeline"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            releases = json.load(resp)
    except Exception as exc:
        return {"weeks": [], "note": f"读取 Releases 失败：{exc}"}
    weeks = []
    for rel in releases:
        tag = rel.get("tag_name", "")
        m = WEEK_TAG_RE.match(tag)
        if not m:
            continue
        files = {}
        for a in rel.get("assets", []) or []:
            files[a["name"]] = {
                "file": a["name"],
                "url": a.get("browser_download_url"),
                "size": a.get("size"),
            }
        # tag 即 ISO 周（data-YYYY-Www），直接算出周一/周日，不再逐个下载 manifest
        start, end = None, None
        try:
            yw = m.group(1)  # YYYY-Www
            y, w = int(yw[:4]), int(yw[6:])
            start = date.fromisocalendar(y, w, 1).isoformat()
            end = date.fromisocalendar(y, w, 7).isoformat()
        except ValueError:
            pass
        weeks.append({"week": m.group(1), "tag": tag, "files": files,
                      "start": start, "end": end,
                      "published_at": rel.get("published_at")})
    weeks.sort(key=lambda w: w["week"], reverse=True)
    return {"weeks": weeks}
