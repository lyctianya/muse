"""AI 对话域装配入口：由 api/main.py 以 prefix="/api/ai" 统一挂载。"""
from .router import router

__all__ = ["router"]
