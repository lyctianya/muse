"""美股数据源：Stooq（主）+ yfinance（备）。

- 现役名单：Nasdaq 官方 nasdaqtraded.txt（免费，覆盖 NYSE/NASDAQ，
  含 ETF；剔除 Test Issue 测试代码）
- 日线（主）：Stooq 免 key CSV 接口
      https://stooq.com/q/d/l/?s={SYM}.us&i=d
  返回 Date,Open,High,Low,Close,Volume；涨跌幅本地计算
- 日线（备）：Stooq 失败时用 yfinance 拉取同区间数据
"""
import csv
import io
import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from fetcher import config
from fetcher.sources import _util

log = logging.getLogger(__name__)
MARKET = "us"
CURRENCY = "USD"

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
STOOQ_URL = "https://stooq.com/q/d/l/?s={sym}.us&i=d"


def _stooq_sym(symbol: str) -> str:
    """Stooq 美股代码规范：小写，BRK.B -> brk-b.us。"""
    return symbol.replace(".", "-").replace("/", "-").lower()


def _yf_sym(symbol: str) -> str:
    """yfinance 美股代码规范：BRK.B -> BRK-B。"""
    return symbol.replace(".", "-")


@_util.retry("美股名单")
def get_symbols() -> list:
    """解析 Nasdaq nasdaqtraded.txt，返回 [(symbol, name), ...]。

    剔除 Test Issue=N 的测试代码；ETF(Y) 与普通股(N) 都保留。
    """
    resp = requests.get(NASDAQ_TRADED_URL, timeout=30)
    resp.raise_for_status()
    out = []
    reader = csv.DictReader(io.StringIO(resp.text), delimiter="|")
    for row in reader:
        try:
            if row.get("Test Issue", "").strip() != "N":
                continue
            symbol = row.get("Symbol", "").strip()
            name = row.get("Security Name", "").strip()
            if not symbol or "/" in symbol and symbol.count("/") > 1:
                continue
            if symbol.startswith("File Creation Time"):
                continue
            out.append((symbol, name[:120]))
        except (AttributeError, KeyError):
            continue
    log.info("美股现役名单：%d 只（含 ETF）", len(out))
    return out


def _parse_stooq(text: str, symbol: str) -> list:
    rows = list(csv.DictReader(io.StringIO(text)))
    bars = []
    prev_close: Optional[float] = None
    for r in rows:
        try:
            if not r.get("Date") or r.get("Close") in (None, "", "N/D"):
                continue
            close = float(r["Close"])
            volume_raw = (r.get("Volume") or "").strip()
            bars.append(
                {
                    "trade_date": pd.to_datetime(r["Date"]).date(),
                    "open": float(r["Open"]),
                    "high": float(r["High"]),
                    "low": float(r["Low"]),
                    "close": close,
                    # 涨跌幅本地计算（相对前一交易日收盘）
                    "pct_change": round((close / prev_close - 1) * 100, 4)
                    if prev_close
                    else None,
                    "volume": int(float(volume_raw)) if volume_raw not in ("", "N/D") else 0,
                    "amount": None,  # Stooq 免费接口不提供成交额
                }
            )
            prev_close = close
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("[%s] 跳过 Stooq 异常行 %s：%s", symbol, r.get("Date"), exc)
    return bars


@_util.retry("Stooq日线")
def _fetch_stooq(symbol: str, start_date: date, end_date: date) -> list:
    url = STOOQ_URL.format(sym=_stooq_sym(symbol))
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    bars = _parse_stooq(resp.text, symbol)
    # 只保留请求区间内的数据
    return [b for b in bars if start_date <= b["trade_date"] <= end_date]


def _yf_download_bars(yf_symbol: str, start_date: date, end_date: date) -> list:
    """yfinance 日线原始抓取（多市场复用，yf_symbol 为 Yahoo 原生代码）。

    auto_adjust=True 即前复权：以最新价为锚向前调整历史 OHLC。
    返回 [dict(trade_date, open, high, low, close, volume, amount, pct_change)]。
    """
    df = yf.download(
        yf_symbol,
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        auto_adjust=True,  # 前复权
        progress=False,
    )
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):  # 新版 yfinance 多层列名
        df.columns = df.columns.get_level_values(0)
    bars = []
    prev_close: Optional[float] = None
    for ts, row in df.iterrows():
        try:
            close = float(row["Close"])
            bars.append(
                {
                    "trade_date": pd.to_datetime(ts).date(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": close,
                    "pct_change": round((close / prev_close - 1) * 100, 4)
                    if prev_close
                    else None,
                    "volume": int(float(row["Volume"])),
                    "amount": None,
                }
            )
            prev_close = close
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("[%s] 跳过 yfinance 异常行 %s：%s", yf_symbol, ts, exc)
    return bars


@_util.retry("yfinance日线")
def _fetch_yfinance(symbol: str, start_date: date, end_date: date) -> list:
    """美股代码 -> Yahoo 代码后抓取（带重试）。"""
    return _yf_download_bars(_yf_sym(symbol), start_date, end_date)


def fetch_bars(symbol: str, start_date: date, end_date: Optional[date] = None) -> list:
    """拉取某只美股自 start_date 起的日线。

    先走 Stooq，失败自动降级到 yfinance；都失败返回 []。
    返回 [dict(trade_date, open, high, low, close, volume, amount, pct_change)]。
    """
    end = end_date or date.today()
    try:
        bars = _fetch_stooq(symbol, start_date, end)
        if bars:
            return bars
        log.warning("[%s] Stooq 返回空，降级到 yfinance", symbol)
    except Exception as exc:  # noqa: BLE001 - 降级逻辑
        log.warning("[%s] Stooq 失败（%s），降级到 yfinance", symbol, exc)
    try:
        return _fetch_yfinance(symbol, start_date, end)
    except Exception as exc:  # noqa: BLE001
        log.error("[%s] yfinance 也失败：%s", symbol, exc)
        return []
