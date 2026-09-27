"""API 公共依赖：配置加载、数据库连接、路径常量。"""
import logging
import os
from pathlib import Path

import psycopg

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


def _conn():
    return psycopg.connect(DATABASE_URL)
