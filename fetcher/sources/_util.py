"""数据源通用小工具：重试（指数退避）+ 请求限速。"""
import functools
import logging
import time

from fetcher import config

log = logging.getLogger(__name__)

_last_call = 0.0


def _throttle() -> None:
    """相邻请求最小间隔，给免费数据源留余量。"""
    global _last_call
    wait = config.REQUEST_MIN_INTERVAL - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def retry(label: str):
    """网络请求重试装饰器：指数退避，重试耗尽后抛异常。"""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = 1.0
            last_exc = None
            for attempt in range(1, config.REQUEST_RETRIES + 1):
                try:
                    _throttle()
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - 重试一切网络/解析异常
                    last_exc = exc
                    log.warning(
                        "%s 第 %d/%d 次失败：%s，%.1fs 后重试",
                        label, attempt, config.REQUEST_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
                    delay *= config.REQUEST_BACKOFF
            raise last_exc

        return wrapper

    return deco
