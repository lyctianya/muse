"""API 公共依赖：配置加载、数据库连接、路径常量。"""
import logging
import os
import threading
from pathlib import Path

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

# 项目根目录：api/deps.py -> stock-data/
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

# 连接串补连接超时（避免网络抖动时请求长时间挂起）
if "connect_timeout" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{sep}connect_timeout=10"

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    """API 全局连接池（懒加载，双重检查锁）。"""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    DATABASE_URL,
                    min_size=2,
                    max_size=10,
                    kwargs={"autocommit": True},
                )
                log.info("API 数据库连接池已创建")
    return _pool


def _conn():
    """取池化连接（上下文管理器），替代每请求新建 TCP 连接。"""
    return _get_pool().connection()


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
