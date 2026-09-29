"""游戏域装配入口：由 api/main.py 以 prefix="/api/game" 统一挂载。"""
from .router import router

__all__ = ["router"]
