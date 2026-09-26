"""出口代理 TLS 指纹补丁（显式 opt-in）。

背景：本机出口代理按 TLS ClientHello 指纹过滤，Python requests 的
指纹访问 eastmoney / bse.cn 等域名时被拒（RemoteDisconnected），
而 curl / 浏览器指纹放行。本补丁把 requests.Session.request 在
命中被封锁域名时转给 curl_cffi（chrome 指纹），其余请求保持原样。

用法：在回填/拉取脚本入口处 `from fetcher.sources import _tls_patch; _tls_patch.apply()`。
只影响当前进程，不修改任何库代码。
"""
import logging
import os

log = logging.getLogger(__name__)

# 被 TLS 指纹封锁的域名（子串匹配）
_BLOCKED_HOSTS = ("eastmoney.com", "bse.cn")

# curl_cffi 支持的 requests 兼容参数（过滤掉不支持的，避免 TypeError）
_SAFE_KWARGS = {
    "params", "data", "headers", "cookies", "files", "auth",
    "timeout", "allow_redirects", "proxies", "verify", "json",
}

_applied = False


def apply() -> bool:
    """应用补丁。返回 True 表示成功启用，False 表示未启用（原因见日志）。"""
    global _applied
    if _applied:
        return True
    try:
        from curl_cffi import requests as crequests
    except ImportError:
        log.warning("curl_cffi 未安装，TLS 补丁未启用；eastmoney/bse.cn 可能不通")
        return False
    import requests

    http_proxy = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
    https_proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    proxies = {"http": http_proxy, "https": https_proxy}

    _orig_request = requests.sessions.Session.request

    def _patched_request(self, method, url, **kwargs):
        if isinstance(url, str) and any(h in url for h in _BLOCKED_HOSTS):
            kwargs = {k: v for k, v in kwargs.items() if k in _SAFE_KWARGS}
            kwargs.setdefault("impersonate", "chrome")
            kwargs.setdefault("proxies", proxies)
            # curl_cffi 在本机出口下会被 tar-pit（曾观测到 300s 才超时），
            # 强制上限 30s 让上层重试逻辑能快速失败、快速重试。
            _t = kwargs.get("timeout", 30)
            try:
                _t = float(_t)
            except (TypeError, ValueError):
                _t = 30
            kwargs["timeout"] = min(_t, 30)
            return crequests.request(method, url, **kwargs)
        return _orig_request(self, method, url, **kwargs)

    requests.sessions.Session.request = _patched_request
    _applied = True
    log.info("TLS 指纹补丁已启用（%s 经 curl_cffi 转发）", ",".join(_BLOCKED_HOSTS))
    return True
