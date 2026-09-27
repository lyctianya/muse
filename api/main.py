"""查询 API + 前端托管。

接口：
    GET /api/symbols?market=cn&q=茅台        搜索股票（market 可选）
    GET /api/bars?market=cn&symbol=600519&from=2026-01-01&to=2026-09-26
    GET /api/weeks                           周文件列表（占位：待周导出任务产出 manifest）

前端构建产物（web/dist）由 StaticFiles 托管在 / 下；
本地开发时 WEB_DIST 默认指向项目根的 web/dist，
Docker 镜像中通过环境变量指向 /app/web_dist。

本地运行：
    cd stock-data && .venv/bin/python -m uvicorn api.main:app --port 8000
"""
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import psycopg
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

log = logging.getLogger(__name__)

# 项目根目录：api/main.py -> stock-data/
ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for raw in dotenv.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
WEB_DIST = Path(os.environ.get("WEB_DIST", str(ROOT / "web" / "dist")))

if not DATABASE_URL:
    raise RuntimeError("未配置 DATABASE_URL（环境变量或 stock-data/.env）")

app = FastAPI(title="股票数据管道 API", version="0.1.0")


def _conn():
    return psycopg.connect(DATABASE_URL)


@app.get("/api/symbols")
def search_symbols(
    market: Optional[str] = Query(default=None, description="cn/hk/us，不传则全市场"),
    q: str = Query(default="", description="代码或名称关键字"),
    limit: int = Query(default=50, le=200),
):
    """搜索股票：按代码/名称模糊匹配，只返回现役（active）股票。"""
    sql = "SELECT market, symbol, name, currency FROM symbols WHERE active = TRUE"
    params: list = []
    if market:
        sql += " AND market = %s"
        params.append(market)
    if q:
        sql += " AND (symbol ILIKE %s OR name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY market, symbol LIMIT %s"
    params.append(limit)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [
        {"market": r[0], "symbol": r[1], "name": r[2], "currency": r[3]}
        for r in rows
    ]


@app.get("/api/bars")
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


@app.get("/api/weeks")
def list_weeks():
    """可下载的周文件列表。

    占位实现：待周导出任务产出 manifest 并接入 GitHub Releases 后，
    这里改为读取 manifest / Release 列表返回真实数据。
    """
    return {"weeks": []}


# ---------------------------------------------------------------- 市场概览（Dashboard）

@app.get("/api/market/overview")
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


@app.get("/api/market/top")
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
                f"""SELECT b.symbol, s.name, b.close, b.pct_change, b.amount
                    FROM daily_bars b
                    JOIN symbols s ON s.market = b.market AND s.symbol = b.symbol
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


@app.get("/api/market/sectors")
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


# ---------------------------------------------------------------- 基本面（A股）

@app.get("/api/company")
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


@app.get("/api/financials")
def get_financials(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    type: str = Query(description="income|balance|cashflow|indicator",
                      pattern="^(income|balance|cashflow|indicator)$"),
):
    """财务三表 / 财务指标：按报告期倒序返回（含提取列 + 原始 data JSON）。"""
    tables = {
        "income": ("fin_income", ["revenue", "net_profit"]),
        "balance": ("fin_balance", ["total_assets", "total_liab"]),
        "cashflow": ("fin_cashflow", []),
        "indicator": ("fin_indicator", ["roe", "gross_margin", "net_margin"]),
    }
    table, extra_cols = tables[type]
    select_extra = ", " + ", ".join(extra_cols) if extra_cols else ""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT report_date{select_extra}, data FROM {table}"
                " WHERE market = %s AND symbol = %s ORDER BY report_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        item = {"report_date": r[0].isoformat(), "data": r[-1]}
        for i, c in enumerate(extra_cols):
            v = r[1 + i]
            item[c] = float(v) if v is not None else None
        out.append(item)
    return out


@app.get("/api/business")
def get_business(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """主营业务构成：按报告期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT report_date, category, item, revenue, revenue_ratio,"
                " profit, profit_ratio FROM main_business"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY report_date DESC, category, revenue DESC NULLS LAST",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "report_date": r[0].isoformat(), "category": r[1], "item": r[2],
            "revenue": r[3], "revenue_ratio": r[4],
            "profit": r[5], "profit_ratio": r[6],
        }
        for r in rows
    ]


@app.get("/api/holders")
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


@app.get("/api/pledge")
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


@app.get("/api/holder-numbers")
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


@app.get("/api/holder-trades")
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


# ---------------------------------------------------------------- 技术指标（本地计算）

def _ema(values: list, period: int) -> list:
    """EMA 序列（与通达信/同花顺一致的递归算法）。"""
    k = 2 / (period + 1)
    out = []
    e = None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


@app.get("/api/tech")
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


@app.get("/api/health")
def health():
    return {"ok": True}


# 前端托管：/api 路由优先，其余全部落到前端单页
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    log.info("前端静态目录已挂载：%s", WEB_DIST)
else:
    log.warning("前端构建产物不存在（%s），仅提供 API；请先 cd web && npm run build", WEB_DIST)
