"""全局配置：从环境变量读取，缺失时尝试加载项目根目录的 .env。

项目根目录约定为本文件上两级（stock-data/）。
敏感信息（数据库密码、GitHub Token）只从环境变量/.env 读取，
绝不写进代码或文档。
"""
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# 项目根目录：fetcher/config.py -> stock-data/
ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """加载 stock-data/.env（若存在），已有的环境变量优先。"""
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return
    for raw in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO: str = os.environ.get("GITHUB_REPO", "")  # 形如 owner/repo
TZ: str = os.environ.get("TZ", "Asia/Shanghai")

# 每个市场允许的并发拉取线程数
FETCH_WORKERS: int = int(os.environ.get("FETCH_WORKERS", "8"))

# 前复权重叠校验阈值：新拉数据与库中重叠日期收盘价偏差超过该比例
# 即判定发生除权除息，触发该股票全历史重拉
ADJUST_SPLIT_THRESHOLD: float = float(os.environ.get("ADJUST_SPLIT_THRESHOLD", "0.005"))

# 网络重试：指数退避
REQUEST_RETRIES: int = int(os.environ.get("REQUEST_RETRIES", "3"))
REQUEST_BACKOFF: float = float(os.environ.get("REQUEST_BACKOFF", "2.0"))
# 相邻请求最小间隔（秒），给免费数据源留余量
REQUEST_MIN_INTERVAL: float = float(os.environ.get("REQUEST_MIN_INTERVAL", "0.2"))

# Tushare Pro（基本面主数据源）
# 直连官方：只设 TUSHARE_TOKEN
# 走中转站（如 DaoShare/teajoin）：TUSHARE_TOKEN 设为平台 API Key，
#   TUSHARE_BASE_URL 设为中转站地址（如 https://teajoin.com）
TUSHARE_TOKEN: str = os.environ.get("TUSHARE_TOKEN", "")
TUSHARE_BASE_URL: str = os.environ.get("TUSHARE_BASE_URL", "").rstrip("/")
# Tushare 调用间隔（秒）。官方 5000 积分档约 500 次/分钟；
# DaoShare 中转站上限 450 次/分钟、建议间隔 ≥0.2 秒，默认 0.2
TUSHARE_MIN_INTERVAL: float = float(os.environ.get("TUSHARE_MIN_INTERVAL", "0.2"))
# Tushare 并发线程数（共享限流；网络 RTT > 间隔时能叠请求加速）
TUSHARE_WORKERS: int = int(os.environ.get("TUSHARE_WORKERS", "6"))


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("未配置 DATABASE_URL（环境变量或 stock-data/.env）")
    return DATABASE_URL
