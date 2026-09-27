"""估值历史分位：基于 daily_basic 近 10 年 PE-TTM / PB 计算分位数。"""
from fastapi import APIRouter, Query

from ..deps import _conn

router = APIRouter()


def _stats(values: list, dates: list) -> dict:
    """分位数统计。values 与 dates 等长、按日期升序。"""
    clean = [(d, v) for d, v in zip(dates, values)
             if v is not None and 0 < v < 1000]
    if not clean:
        return {"found": False, "count": 0}
    ds = [d for d, _ in clean]
    vs = sorted(v for _, v in clean)
    n = len(vs)
    cur = clean[-1][1]  # 最新值

    def pct(p: float) -> float:
        # 线性插值分位数
        if n == 1:
            return vs[0]
        k = (n - 1) * p / 100
        f = int(k)
        c = k - f
        return vs[f] + (vs[f + 1] - vs[f]) * c if f + 1 < n else vs[f]

    le = sum(1 for v in vs if v <= cur)
    span_days = (ds[-1] - ds[0]).days if len(ds) > 1 else 0
    r2 = lambda x: round(x, 2)
    return {
        "found": True,
        "count": n,
        "span_years": round(span_days / 365.25, 1),
        "trade_date": ds[-1].isoformat(),
        "current": r2(cur),
        "min": r2(vs[0]),
        "q10": r2(pct(10)),
        "q25": r2(pct(25)),
        "median": r2(pct(50)),
        "q75": r2(pct(75)),
        "q90": r2(pct(90)),
        "max": r2(vs[-1]),
        "quantile": round(le / n * 100, 1),
    }


@router.get("/api/valuation-quantile")
def valuation_quantile(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """估值历史分位：PE-TTM / PB 在全部历史中的百分位（越低越便宜）。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, pe_ttm, pb FROM daily_basic"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY trade_date",
                (market, symbol),
            )
            rows = cur.fetchall()
    if not rows:
        return {"symbol": symbol, "found": False}
    dates = [r[0] for r in rows]
    pe = _stats([r[1] for r in rows], dates)
    pb = _stats([r[2] for r in rows], dates)
    if not pe["found"] and not pb["found"]:
        return {"symbol": symbol, "found": False}
    return {
        "symbol": symbol,
        "found": True,
        "trade_date": dates[-1].isoformat(),
        "pe_ttm": pe,
        "pb": pb,
    }
