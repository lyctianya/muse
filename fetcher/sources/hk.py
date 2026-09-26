"""港股数据源。

现役名单（按优先级）：
1. 港交所官方 ListOfSecurities.xlsx（权威；但偶发返回残缺文件，<1500 行时弃用）
2. Yahoo Finance HKG screener（EQUITY + ETF，exchange=HKG）—— 本机网络下可用

日线：yfinance（<代码>.HK），auto_adjust=True（前复权）
代码统一存 5 位（如 00700）；抓取时映射为 Yahoo 符号 0700.HK。
"""
import io
import json
import logging
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional

import requests

from fetcher.sources import _util
from fetcher.sources.us import _yf_download_bars

log = logging.getLogger(__name__)
MARKET = "hk"
CURRENCY = "HKD"

_CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "hk_symbols.json"
_CACHE_TTL = 24 * 3600  # 名单缓存 24 小时：screener 接口限流频繁，避免每次运行都重新枚举

_HKEX_XLSX_URL = (
    "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/"
    "ListOfSecurities.xlsx"
)
_HKEX_MIN_ROWS = 1500  # 低于此行数视为残缺文件，降级到 Yahoo
_HKEX_WANT_CATEGORIES = {"Equity", "Exchange Traded Products", "Real Estate Investment Trusts"}

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def _norm_code(raw: str) -> str:
    """港股代码统一为 5 位，保留前导零，如 700 -> 00700。"""
    code = "".join(ch for ch in str(raw).strip() if ch.isdigit())
    return code.zfill(5)


def _to_yahoo(symbol_5d: str) -> str:
    """5 位代码 -> Yahoo 符号：00700 -> 0700.HK（去一个前导零）。"""
    return symbol_5d[1:] + ".HK"


def _hkex_symbols() -> list:
    """从港交所官方 xlsx 解析现役名单；解析失败/残缺返回 []。"""
    import openpyxl

    r = requests.get(_HKEX_XLSX_URL, timeout=60, headers={"User-Agent": _UA})
    r.raise_for_status()
    wb = openpyxl.load_workbook(filename=io.BytesIO(r.content), read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    header_idx = code_i = name_i = cat_i = None
    for i, row in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in row]
        if cells and cells[0] == "Stock Code":
            header_idx, code_i = i, 0
            name_i = cells.index("Name of Securities") if "Name of Securities" in cells else 1
            cat_i = cells.index("Category") if "Category" in cells else 2
            break
    if header_idx is None:
        return []
    out = []
    for row in rows[header_idx + 1:]:
        code = _norm_code(row[code_i]) if row[code_i] else ""
        name = str(row[name_i]).strip() if row[name_i] else ""
        cat = str(row[cat_i]).strip() if row[cat_i] else ""
        if len(code) == 5 and cat in _HKEX_WANT_CATEGORIES and name:
            out.append((code, name))
    return out


def _yahoo_session():
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    s.get("https://fc.yahoo.com", timeout=20)
    crumb = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=20).text.strip()
    return s, crumb


def _screener_page(s, crumb, quote_type: str, offset: int, size: int = 500):
    body = {
        "size": size,
        "offset": offset,
        "sortField": "ticker",
        "sortType": "ASC",
        "quoteType": quote_type,
        "query": {"operator": "AND", "operands": [{"operator": "eq", "operands": ["exchange", "HKG"]}]},
        "userId": "",
        "userIdType": "guid",
    }
    r = s.post(
        "https://query2.finance.yahoo.com/v1/finance/screener?crumb=" + crumb,
        json=body,
        timeout=30,
    )
    res = r.json()["finance"]["result"][0]
    return res["total"], res["quotes"] or []


def _yahoo_symbols() -> list:
    """Yahoo screener 枚举全部 HKG 上市的股票 + ETF（温和分页，避免限流）。"""
    out: dict = {}
    s, crumb = _yahoo_session()
    for qt in ("EQUITY", "ETF"):
        offset = 0
        while True:
            for attempt in range(4):
                try:
                    total, quotes = _screener_page(s, crumb, qt, offset)
                    break
                except Exception:
                    time.sleep(2 * (attempt + 1))
                    s, crumb = _yahoo_session()  # crumb 可能过期，刷新会话
            else:
                raise RuntimeError("Yahoo screener 多次失败")
            for q in quotes:
                m = re.match(r"^(\d{4})\.HK$", q.get("symbol", ""))
                if not m:
                    continue
                code = m.group(1).zfill(5)
                name = (q.get("shortName") or q.get("longName") or "").strip()
                if code not in out:
                    out[code] = name or code
            offset += len(quotes)
            if offset >= total or not quotes:
                break
            time.sleep(1.5)
    return sorted(out.items())


def _load_cache() -> Optional[list]:
    try:
        if _CACHE_FILE.exists() and time.time() - _CACHE_FILE.stat().st_mtime < _CACHE_TTL:
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            out = [(d["code"], d["name"]) for d in data if d.get("code")]
            if len(out) >= _HKEX_MIN_ROWS:
                return out
    except Exception:  # noqa: BLE001 - 缓存损坏就当没有
        pass
    return None


def _save_cache(symbols: list) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps([{"code": c, "name": n} for c, n in symbols], ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("写港股名单缓存失败：%s", exc)


@_util.retry("港股名单")
def get_symbols() -> list:
    """返回 [(symbol, name), ...]，symbol 为 5 位代码（如 00700）。"""
    cached = _load_cache()
    if cached:
        log.info("港股现役名单（本地缓存）：%d 只", len(cached))
        return cached
    try:
        hkex = _hkex_symbols()
    except Exception as exc:  # noqa: BLE001 - 降级逻辑
        log.warning("港交所名单下载失败，走 Yahoo 备用：%s", exc)
        hkex = []
    if len(hkex) >= _HKEX_MIN_ROWS:
        log.info("港股现役名单（港交所官方）：%d 只", len(hkex))
        _save_cache(hkex)
        return hkex
    log.warning("港交所名单仅 %d 行（<%d，疑似残缺），降级到 Yahoo screener", len(hkex), _HKEX_MIN_ROWS)
    out = _yahoo_symbols()
    log.info("港股现役名单（Yahoo）：%d 只", len(out))
    _save_cache(out)
    return out


@_util.retry("港股日线")
def fetch_bars(symbol: str, start_date: date, end_date: Optional[date] = None) -> list:
    """拉取某只港股自 start_date 起的日线（前复权）。

    返回 [dict(trade_date, open, high, low, close, volume, amount, pct_change)]；
    无数据时返回 []。
    """
    end = end_date or date.today()
    return _yf_download_bars(_to_yahoo(symbol), start_date, end)
