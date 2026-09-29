"""股票域：行情/公司/财务/选股/同步等全部路由的装配入口。

由 api/main.py 以 prefix="/api/stock" 统一挂载；
各子路由内部只写相对路径（如 /bars），不再带 /api 前缀。
"""
from fastapi import APIRouter, Depends

from api.platform.auth import require_perm

from .routers import (
    company,
    financials,
    holders,
    market,
    quotes,
    screener,
    sync,
    tech,
    tushare,
    tushare_full,
    valuation,
    watchlist,
)

router = APIRouter()

router.include_router(quotes.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(market.router, dependencies=[Depends(require_perm("market:view"))])
router.include_router(company.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(financials.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(holders.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(tech.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(tushare.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(tushare_full.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(sync.router, dependencies=[Depends(require_perm("sync:view"))])
router.include_router(screener.router, dependencies=[Depends(require_perm("screener:use"))])
router.include_router(valuation.router, dependencies=[Depends(require_perm("quotes:view"))])
router.include_router(watchlist.router, dependencies=[Depends(require_perm("watchlist:use"))])
