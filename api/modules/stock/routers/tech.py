"""技术指标（MACD/KDJ/BOLL，基于前复权收盘价本地计算）。"""
from datetime import date

from fastapi import APIRouter, Query

from api.platform.deps import _conn

router = APIRouter()


def _ema(values: list, period: int) -> list:
    """EMA 序列（与通达信/同花顺一致的递归算法）。"""
    k = 2 / (period + 1)
    out = []
    e = None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


@router.get("/tech")
def get_tech(
    market: str = Query(description="cn/hk/us"),
    symbol: str = Query(description="股票代码，如 600519"),
    from_: date = Query(alias="from", description="起始日期 YYYY-MM-DD"),
    to: date = Query(alias="to", description="结束日期 YYYY-MM-DD"),
    indicator: str = Query(default="macd", description="macd|kdj|boll",
                          pattern="^(macd|kdj|boll)$"),
):
    """技术指标（基于前复权收盘价本地计算）。

    为保证指标预热，会自动向前多取 60 个交易日，返回区间与 from/to 对齐。
    """
    warmup = 60
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, open, high, low, close, volume"
                " FROM daily_bars WHERE market = %s AND symbol = %s"
                " AND trade_date <= %s ORDER BY trade_date DESC LIMIT 10000",
                (market, symbol, to),
            )
            rows = cur.fetchall()
    rows.reverse()  # 升序
    # 定位 from_ 起点（含预热）
    idx = next((i for i, r in enumerate(rows) if r[0] >= from_), len(rows))
    start = max(0, idx - warmup)
    seq = rows[start:]
    dates = [r[0].isoformat() for r in seq]
    closes = [r[4] for r in seq]

    result = {"indicator": indicator, "dates": [], "values": []}
    if indicator == "macd":
        dif = [a - b for a, b in zip(_ema(closes, 12), _ema(closes, 26))]
        dea = _ema(dif, 9)
        macd = [2 * (d - e) for d, e in zip(dif, dea)]
        vals = list(zip(dif, dea, macd))
    elif indicator == "kdj":
        vals = []
        for i in range(len(seq)):
            window = seq[max(0, i - 8):i + 1]
            low_n = min(r[3] for r in window)
            high_n = max(r[2] for r in window)
            rsv = 50.0 if high_n == low_n else (seq[i][4] - low_n) / (high_n - low_n) * 100
            if not vals:
                k = d = 50.0
            else:
                k = 2 / 3 * vals[-1][0] + 1 / 3 * rsv
                d = 2 / 3 * vals[-1][1] + 1 / 3 * k
            j = 3 * k - 2 * d
            vals.append((k, d, j))
    else:  # boll
        vals = []
        for i in range(len(seq)):
            window = closes[max(0, i - 19):i + 1]
            n = len(window)
            ma = sum(window) / n
            var = sum((x - ma) ** 2 for x in window) / n
            sd = var ** 0.5
            vals.append((ma + 2 * sd, ma, ma - 2 * sd))

    # 裁掉预热区，只返回 from_ 起
    cut = idx - start
    result["dates"] = dates[cut:]
    result["values"] = [list(v) for v in vals[cut:]]
    result["columns"] = {
        "macd": ["dif", "dea", "macd"],
        "kdj": ["k", "d", "j"],
        "boll": ["upper", "mid", "lower"],
    }[indicator]
    return result
