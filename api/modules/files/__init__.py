"""文件域装配入口：由 api/main.py 以 prefix="/api/files" 统一挂载。"""
from .router import router

__all__ = ["router"]
