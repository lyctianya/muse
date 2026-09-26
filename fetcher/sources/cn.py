"""A股数据源：AkShare。

- 现役名单：stock_info_a_code_name() —— 天然不含退市，含北交所；ST/*ST 保留
- 日线：stock_zh_a_hist(adjust="qfq") —— 前复权
- 注意：AkShare 返回的成交量单位为“手”，成交额单位为元
"""
import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd

from fetcher.sources import _util

log = logging.getLogger(__name__)
MARKET = "cn"
CURRENCY = "CNY"

# 名单本地缓存（24h 有效；交易所官网间歇性抽风时兜底）
_CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "cn_symbols.json"
_CACHE_TTL = 24 * 3600

# AkShare 日期参数格式：YYYYMMDD
_FMT = "%Y%m%d"


def _load_cache() -> list:
    """读取本地缓存名单，返回 [(symbol, name)]，无缓存/过期返回 []。"""
    try:
        if not _CACHE_FILE.exists():
            return []
        if time.time() - _CACHE_FILE.stat().st_mtime > _CACHE_TTL:
            return []
        items = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return [(str(it["code"]).zfill(6), str(it.get("name") or it["code"])) for it in items]
    except Exception:
        return []


def _save_cache(symbols: list) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps([{"code": c, "name": n} for c, n in symbols], ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("A股名单缓存写入失败：%s", exc)


@_util.retry("A股名单")
def _fetch_symbols_fresh() -> list:
    """从交易所官网拉取现役名单（可能间歇性失败，由 retry 包裹）。"""
    df = ak.stock_info_a_code_name()
    # 列名兼容：新版 akshare 用 code/name，旧版用 代码/名称
    code_col = "代码" if "代码" in df.columns else "code"
    name_col = "名称" if "名称" in df.columns else "name"
    out = []
    for _, row in df.iterrows():
        code = str(row[code_col]).strip().zfill(6)
        name = str(row[name_col]).strip()
        if len(code) == 6 and code.isdigit():
            out.append((code, name))
    log.info("A股现役名单：%d 只", len(out))
    return out


def get_symbols() -> list:
    """返回 [(symbol, name), ...]，symbol 为 6 位代码。

    优先用 24h 内本地缓存（名单变化慢）；缓存过期/缺失时才拉取最新，
    拉取失败则回退到过期缓存。
    """
    syms = _load_cache()
    if syms:
        log.info("A股现役名单（本地缓存）：%d 只", len(syms))
        return syms
    try:
        syms = _fetch_symbols_fresh()
    except Exception as exc:
        log.warning("A股名单拉取失败：%s", str(exc)[-100:])
        syms = []
    if syms:
        _save_cache(syms)
    else:
        # 缓存过期了也比没有强
        try:
            items = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            syms = [(str(it["code"]).zfill(6), str(it.get("name") or it["code"])) for it in items]
            if syms:
                log.warning("A股现役名单（过期缓存兜底）：%d 只", len(syms))
        except Exception:
            pass
    if not syms:
        raise RuntimeError("A股名单拉取失败且无本地缓存")
    return syms


def _pick(df: pd.DataFrame, *names: str) -> Optional[pd.Series]:
    for n in names:
        if n in df.columns:
            return df[n]
    return None


@_util.retry("A股日线")
def _fetch_akshare(symbol: str, start_date: date, end_date: date) -> list:
    """经 AkShare 拉取前复权日线（fqt=1）。"""
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date.strftime(_FMT),
        end_date=end_date.strftime(_FMT),
        adjust="qfq",
    )
    if df is None or df.empty:
        return []
    bars = []
    for _, row in df.iterrows():
        try:
            bars.append(
                {
                    "trade_date": pd.to_datetime(row["日期"]).date(),
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": int(float(row["成交量"])),  # 单位：手
                    "amount": float(row["成交额"]) if "成交额" in df.columns else None,
                    "pct_change": float(row["涨跌幅"]) if "涨跌幅" in df.columns else None,
                }
            )
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("[%s] 跳过异常行 %s：%s", symbol, row.get("日期"), exc)
    return bars


def _sane(bars: list) -> bool:
    """校验前复权 OHLC：价格为正且 low <= open/close <= high。

    东方财富 fqt=1 对个别股票的老日期会返回错乱数据（如负数），
    用此校验拦截，坏行超过 5% 即视为整批不可信。
    """
    if not bars:
        return True
    bad = 0
    for b in bars:
        o, h, l, c = b["open"], b["high"], b["low"], b["close"]
        if not (o > 0 and h > 0 and l > 0 and c > 0):
            bad += 1
        elif not (l <= min(o, c) <= max(o, c) <= h):
            bad += 1
    return bad / len(bars) <= 0.05


def _yf_symbol(symbol: str) -> Optional[str]:
    """A股代码转 Yahoo 代码；北交所 yfinance 不支持，返回 None。"""
    if symbol.startswith("6"):
        return symbol + ".SS"
    if symbol[0] in ("0", "3"):
        return symbol + ".SZ"
    return None  # 4/8 开头北交所等


def fetch_bars(symbol: str, start_date: date, end_date: Optional[date] = None) -> list:
    """拉取某只 A股自 start_date 起的日线（前复权）。

    主力走 AkShare/东方财富 fqt=1；若返回数据校验失败（东方财富
    对个别股票老日期的前复权错乱），自动切 yfinance 兜底。
    北交所无 yfinance 覆盖，保留 AkShare 结果（其日期较新不受影响）。

    返回 [dict(trade_date, open, high, low, close, volume, amount, pct_change)]
    trade_date 为 datetime.date；无数据时返回 []。
    """
    end = end_date or date.today()
    bars = _fetch_akshare(symbol, start_date, end)
    if bars and not _sane(bars):
        yf_sym = _yf_symbol(symbol)
        if yf_sym:
            log.warning("[%s] AkShare 前复权校验失败，切 yfinance 兜底", symbol)
            from fetcher.sources.us import _yf_download_bars

            bars = _yf_download_bars(yf_sym, start_date, end)
        else:
            log.warning("[%s] AkShare 前复权校验失败且无 yfinance 覆盖，保留原数据", symbol)
    return bars
