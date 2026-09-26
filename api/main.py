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


@app.get("/api/health")
def health():
    return {"ok": True}


# 前端托管：/api 路由优先，其余全部落到前端单页
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    log.info("前端静态目录已挂载：%s", WEB_DIST)
else:
    log.warning("前端构建产物不存在（%s），仅提供 API；请先 cd web && npm run build", WEB_DIST)
