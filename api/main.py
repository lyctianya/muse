"""查询 API + 前端托管（路由按业务域拆分到 api/routers/）。

接口：
    认证      api/routers/auth.py        /api/auth/*, /api/users, /api/roles
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
                                        /api/managers, /api/share-float,
                                        /api/block-trade, /api/adj-factor,
                                        /api/repurchase, /api/pledge-detail,
                                        /api/index-basic, /api/index-weight,
                                        /api/index-member, /api/cyq,
                                        /api/hk-hold
    同步管理  api/routers/sync.py        /api/sync/status, /api/sync/refresh-status,
                                        /api/sync/run, /api/sync/jobs
    策略选股  api/routers/screener.py    /api/screener/fields, /api/screener/run
    估值分位  api/routers/valuation.py   /api/valuation-quantile
    自选股    api/routers/watchlist.py   /api/watchlist（GET/POST/PUT/DELETE）
    健康检查  api/routers/health.py      /api/health

权限：除 /api/auth/* 与 /api/health 外，其余接口按路由挂 require_perm 守卫。

前端构建产物（web/dist）由 StaticFiles 托管在 / 下；
本地开发时 WEB_DIST 默认指向项目根的 web/dist，
Docker 镜像中通过环境变量指向 /app/web_dist。

本地运行：
    cd stock-data && .venv/bin/python -m uvicorn api.main:app --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from .deps import WEB_DIST, close_pool, log
from .routers import (
    auth, company, financials, health, holders, market, quotes, screener, sync,
    tech, tushare, tushare_full, valuation, watchlist,
)
from .routers.auth import ensure_admin_seed, require_perm


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_admin_seed()
    except Exception as exc:  # noqa: BLE001
        log.warning("admin 种子初始化失败：%s", exc)
    yield
    close_pool()
    log.info("API 数据库连接池已关闭")


app = FastAPI(title="股票数据管道 API", version="0.1.0", lifespan=lifespan)

# 认证（公开）与健康检查（公开）
app.include_router(auth.router)
app.include_router(health.router)

# 业务路由：按域挂权限守卫
app.include_router(quotes.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(market.router, dependencies=[Depends(require_perm("market:view"))])
app.include_router(company.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(financials.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(holders.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(tech.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(tushare.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(tushare_full.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(sync.router, dependencies=[Depends(require_perm("sync:view"))])
app.include_router(screener.router, dependencies=[Depends(require_perm("screener:use"))])
app.include_router(valuation.router, dependencies=[Depends(require_perm("quotes:view"))])
app.include_router(watchlist.router, dependencies=[Depends(require_perm("watchlist:use"))])


# 前端托管：/api 路由优先，其余全部落到前端单页
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    log.info("前端静态目录已挂载：%s", WEB_DIST)
else:
    log.warning("前端构建产物不存在（%s），仅提供 API；请先 cd web && npm run build", WEB_DIST)
