"""多域应用装配层：注册 platform（认证/健康）与各业务模块路由。

路由命名空间：
    认证/用户   /api/auth/*, /api/users, /api/roles   api/platform/auth.py
    健康检查   /api/health                           api/platform/health.py
    股票域     /api/stock/*                          api/modules/stock/
    文件域     /api/files/*                          api/modules/files/
    博客域     /api/blog/*                           api/modules/blog/
    相册域     /api/gallery/*                        api/modules/gallery/
    游戏域     /api/game/*                           api/modules/game/
    新闻60秒   /api/news60s/*                        api/modules/news60s/

新模块接入：在 api/modules/<domain>/ 下建包并导出 router，
main.py 里加一行 include_router 即可。

本地运行：
    cd stock-data && .venv/bin/python -m uvicorn api.main:app --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.modules.blog import router as blog_router
from api.modules.files import router as files_router
from api.modules.gallery import router as gallery_router
from api.modules.game import router as game_router
from api.modules.news60s import router as news60s_router
from api.modules.news60s import start_sync_loop, stop_sync_loop
from api.modules.stock import router as stock_router
from api.platform import auth, health
from api.platform.auth import ensure_admin_seed
from api.platform.deps import WEB_DIST, close_pool, log


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_admin_seed()
    except Exception as exc:  # noqa: BLE001
        log.warning("admin 种子初始化失败：%s", exc)
    try:
        start_sync_loop()
    except Exception as exc:  # noqa: BLE001
        log.warning("news60s 同步线程启动失败：%s", exc)
    yield
    stop_sync_loop()
    close_pool()
    log.info("API 数据库连接池已关闭")


app = FastAPI(title="Muse 多域应用 API", version="0.2.0", lifespan=lifespan)

# 平台层：认证（公开）与健康检查（公开）
app.include_router(auth.router)
app.include_router(health.router)

# 业务模块：按域挂前缀
app.include_router(stock_router, prefix="/api/stock")
app.include_router(files_router, prefix="/api/files")
app.include_router(blog_router, prefix="/api/blog")
app.include_router(gallery_router, prefix="/api/gallery")
app.include_router(game_router, prefix="/api/game")
app.include_router(news60s_router, prefix="/api/news60s")


# 前端托管：/api 路由优先，其余全部落到前端单页
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    log.info("前端静态目录已挂载：%s", WEB_DIST)
else:
    log.warning("前端构建产物不存在（%s），仅提供 API；请先 cd web && npm run build", WEB_DIST)
