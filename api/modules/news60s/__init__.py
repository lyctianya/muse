"""新闻60秒域装配入口：由 api/main.py 以 prefix="/api/news60s" 统一挂载。"""
from .router import router, start_sync_loop, stop_sync_loop

__all__ = ["router", "start_sync_loop", "stop_sync_loop"]
