"""查询 API + 前端托管（路由按业务域拆分到 api/routers/）。

接口：
    行情      api/routers/quotes.py      /api/symbols, /api/bars, /api/weeks
    市场概览  api/routers/market.py      /api/market/overview, /api/market/top,
                                        /api/market/sectors
    公司      api/routers/company.py     /api/company
    财务      api/routers/financials.py  /api/financials, /api/business
    股东      api/routers/holders.py     /api/holders, /api/pledge,
                                        /api/holder-numbers, /api/holder-trades
    技术指标  api/routers/tech.py        /api/tech
    Tushare   api/routers/tushare.py     /api/daily-basic, /api/dividend,
                                        /api/forecast, /api/express,
                                        /api/moneyflow, /api/suspend
    全量接口  api/routers/tushare_full.py  /api/mainbz, /api/company-detail,
                                        /api/namechange, /api/top-list,
                                        /api/top-inst, /api/index-daily,
                                        /api/hsgt-flow, /api/hsgt-top10,
                                        /api/disclosure, /api/margin,
                                        /api/margin-detail, /api/stk-limit,
                                        /api/fina-audit, /api/new-share,
                                        /api/managers
    同步管理  api/routers/sync.py        /api/sync/status, /api/sync/run,
                                        /api/sync/jobs
    健康检查  api/routers/health.py      /api/health

前端构建产物（web/dist）由 StaticFiles 托管在 / 下；
本地开发时 WEB_DIST 默认指向项目根的 web/dist，
Docker 镜像中通过环境变量指向 /app/web_dist。

本地运行：
    cd stock-data && .venv/bin/python -m uvicorn api.main:app --port 8000
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .deps import WEB_DIST, log
from .routers import (
    company, financials, health, holders, market, quotes, sync, tech,
    tushare, tushare_full,
)

app = FastAPI(title="股票数据管道 API", version="0.1.0")

app.include_router(quotes.router)
app.include_router(market.router)
app.include_router(company.router)
app.include_router(financials.router)
app.include_router(holders.router)
app.include_router(tech.router)
app.include_router(tushare.router)
app.include_router(tushare_full.router)
app.include_router(sync.router)
app.include_router(health.router)


# 前端托管：/api 路由优先，其余全部落到前端单页
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    log.info("前端静态目录已挂载：%s", WEB_DIST)
else:
    log.warning("前端构建产物不存在（%s），仅提供 API；请先 cd web && npm run build", WEB_DIST)
