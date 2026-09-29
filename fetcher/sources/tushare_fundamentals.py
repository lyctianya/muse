"""Tushare Pro 基本面数据源（A股）。

覆盖 8 张表：
- company_info   <- stock_basic + daily_basic（最新 PE/PB/市值）
- fin_income     <- income（利润表）
- fin_balance    <- balancesheet（资产负债表）
- fin_cashflow   <- cashflow（现金流量表）
- fin_indicator  <- fina_indicator（财务指标：ROE/毛利率/净利率）
- top_holders    <- top10_holders + top10_floatholders
- holder_number  <- stk_holdernumber（股东户数）
- pledge_info    <- pledge_stat（质押统计）

Tushare 没有的表（main_business 主营构成、holder_trade 增减持）
走东方财富 best-effort 补充，失败则跳过。

只需近 2 年数据。需要 TUSHARE_TOKEN 环境变量。
"""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Callable, Iterable, Optional

import pandas as pd

from fetcher import config, db
from fetcher.sources import _util

log = logging.getLogger(__name__)

_pro = None
_last_call = 0.0
_call_lock = threading.Lock()
_ts_lock = threading.Lock()


_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
_relay_patched = False
_relay_lock = threading.Lock()


def _patch_relay_headers() -> None:
    """中转站的 WAF 会拦截无浏览器头的请求，这里给发往中转站的
    requests.post 补上浏览器头。仅在 TUSHARE_BASE_URL 启用时生效，
    直连官方 API 时不做任何改动。"""
    global _relay_patched
    with _relay_lock:
        if _relay_patched or not config.TUSHARE_BASE_URL:
            return
        import requests as _requests
        _orig_post = _requests.post
        base = config.TUSHARE_BASE_URL

        def _post(url, *args, **kwargs):
            if str(url).startswith(base):
                headers = dict(kwargs.pop("headers", None) or {})
                headers.setdefault("User-Agent", _BROWSER_UA)
                headers.setdefault("Accept", "application/json")
                headers.setdefault("Referer", base + "/guide")
                kwargs["headers"] = headers
            return _orig_post(url, *args, **kwargs)

        _requests.post = _post
        _relay_patched = True


def _ts():
    """Tushare Pro 客户端单例。"""
    global _pro
    if _pro is None:
        with _ts_lock:
            if _pro is None:
                if not config.TUSHARE_TOKEN:
                    raise RuntimeError("未配置 TUSHARE_TOKEN 环境变量")
                _patch_relay_headers()
                import tushare as ts
                ts.set_token(config.TUSHARE_TOKEN)
                pro = ts.pro_api(timeout=30)
                pro._DataApi_token = config.TUSHARE_TOKEN
                if config.TUSHARE_BASE_URL:
                    # 中转站模式（如 DaoShare/teajoin）：把请求指向中转站地址，
                    # 协议与官方 Tushare 完全兼容，token 用平台 API Key
                    pro._DataApi__http_url = config.TUSHARE_BASE_URL
                _pro = pro
    return _pro


def _throttle() -> None:
    """线程安全限流：控制请求启动间隔，允许多请求同时在途。"""
    global _last_call
    with _call_lock:
        wait = config.TUSHARE_MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


def _call(api_name: str, **params) -> pd.DataFrame:
    """带限速的 Tushare 调用，返回 DataFrame（空表表示无数据）。"""
    _throttle()
    pro = _ts()
    fn = getattr(pro, api_name)
    last_exc = None
    delay = 1.0
    for attempt in range(1, config.REQUEST_RETRIES + 1):
        try:
            return fn(**params)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            # 积分不足 / 权限不足不重试，直接抛
            msg = str(exc)
            if "权限" in msg or "积分" in msg or "token" in msg.lower():
                raise
            log.warning("tushare.%s 第 %d/%d 次失败：%s，%.1fs 后重试",
                        api_name, attempt, config.REQUEST_RETRIES, exc, delay)
            time.sleep(delay)
            delay *= config.REQUEST_BACKOFF
    raise last_exc


def _ts_code(symbol: str) -> str:
    """600519 -> 600519.SH；000001 -> 000001.SZ。"""
    s = symbol.strip()
    if s.startswith(("6", "9")):
        return f"{s}.SH"
    if s.startswith(("4", "8")):
        return f"{s}.BJ"
    return f"{s}.SZ"


def _plain(symbol_ts: str) -> str:
    return symbol_ts.split(".")[0]


def _cutoff() -> date:
    t = date.today()
    try:
        return t.replace(year=t.year - 2)
    except ValueError:
        return t.replace(year=t.year - 2, day=28)


def _period_range() -> tuple:
    """近 2 年区间，返回 (start_date, end_date) YYYYMMDD 字符串。"""
    return _cutoff().strftime("%Y%m%d"), date.today().strftime("%Y%m%d")


def _incremental_start(
    from_date: str,
    table: str,
    date_col: str,
    default: date,
) -> date:
    """解析增量起点：显式 from_date > sync_status.latest_date > 库内 max > default。

    有水位/库内日期时从该日重拉（覆盖当日更新），避免漏数。
    优先读 sync_status，避免每次对业务表做 MAX 全表扫描。
    """
    explicit = _to_date(from_date)
    if explicit:
        return explicit
    if not table.replace("_", "").isalnum() or not date_col.replace("_", "").isalnum():
        return default

    # 1) 同步水位表
    try:
        from fetcher import sync_status as ss
        latest = ss.get_latest(table)
        if latest:
            log.info("%s 增量：sync_status.latest_date=%s", table, latest)
            return latest
    except Exception as exc:  # noqa: BLE001
        log.warning("读 sync_status[%s] 失败：%s", table, exc)

    # 2) 回退：扫业务表一次，并回写水位
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT max({date_col}) FROM {table}")  # noqa: S608
            row = cur.fetchone()
            if row and row[0]:
                log.info("%s 增量：库内 max(%s)=%s（回写 sync_status）",
                         table, date_col, row[0])
                try:
                    from fetcher import sync_status as ss
                    ss.upsert(table, latest_date=row[0])
                except Exception:  # noqa: BLE001
                    pass
                return row[0]
    except Exception as exc:  # noqa: BLE001
        log.warning("查询 %s.%s 失败，回退默认起点 %s：%s",
                    table, date_col, default, exc)
    return default


def _symbol_max_dates(table: str, date_col: str) -> dict:
    """返回 {symbol: max(date_col)}，表为空则 {}。"""
    if not table.replace("_", "").isalnum() or not date_col.replace("_", "").isalnum():
        return {}
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT symbol, max({date_col}) FROM {table} "  # noqa: S608
                f"WHERE market='cn' GROUP BY symbol"
            )
            return {r[0]: r[1] for r in cur.fetchall() if r[1] is not None}
    except Exception as exc:  # noqa: BLE001
        log.warning("查询 %s 分股票 max(%s) 失败：%s", table, date_col, exc)
        return {}


def _workers() -> int:
    return max(1, int(config.TUSHARE_WORKERS))


def _parallel_map(
    items: Iterable,
    fn: Callable,
    label: str,
    *,
    log_every: int = 100,
) -> int:
    """并发执行 fn(item)->int（返回写入行数），共享 Tushare 限流。

    失败项在末尾重试一次；仍失败则抛 RuntimeError 中断任务，
    避免异常被吞后水位越过失败项形成永久缺口。
    """
    items = list(items)
    workers = _workers()
    log.info("%s 待处理 %d 项，workers=%d", label, len(items), workers)
    if not items:
        return 0
    t0 = time.time()
    total = 0
    done = 0
    failed: list = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fn, item): item for item in items}
        for fut in as_completed(futs):
            item = futs[fut]
            done += 1
            try:
                total += int(fut.result() or 0)
            except Exception as exc:  # noqa: BLE001
                failed.append(item)
                log.warning("%s [%s] 失败：%s", label, item, exc)
            if done % log_every == 0 or done == len(items):
                log.info("%s 进度 %d/%d，累计 %d 行，失败 %d，%.1fs",
                         label, done, len(items), total, len(failed),
                         time.time() - t0)
    # 失败项串行重试一次
    if failed:
        log.info("%s 失败 %d 项，开始重试", label, len(failed))
        retry_failed = []
        for item in failed:
            try:
                total += int(fn(item) or 0)
            except Exception as exc:  # noqa: BLE001
                retry_failed.append(item)
                log.warning("%s [%s] 重试仍失败：%s", label, item, exc)
        failed = retry_failed
    log.info("%s 完成：%d 行，失败 %d，%.1fs",
             label, total, len(failed), time.time() - t0)
    if failed:
        raise RuntimeError(
            f"{label} 有 {len(failed)} 项失败（已重试）：{failed[:20]}"
            + ("..." if len(failed) > 20 else "")
            + "，请检查日志后用 --from-date 断点续跑")
    return total


def _to_date(v) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s in ("--", "-", "None"):
        return None
    s = s[:10].replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s if fmt == "%Y-%m-%d" else s.replace("-", ""),
                                     fmt).date()
        except ValueError:
            continue
    return None


def _to_float(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        s = str(v).strip().replace(",", "")
        if s in ("", "--", "-", "None"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _row_json(row: pd.Series) -> str:
    return json.dumps({str(k): (None if pd.isna(v) else str(v))
                       for k, v in row.items()}, ensure_ascii=False)


def _periods() -> list:
    """近 2 年已结束季度的季度末 YYYYMMDD 列表（倒序，共 8 个）。

    持续回退直到凑满 8 个已结束季度（当前未结束季度自动跳过）。
    """
    out = []
    t = date.today()
    y, m = t.year, t.month
    qm = ((m - 1) // 3 + 1) * 3
    while len(out) < 8:
        if qm == 12:
            qe = date(y, 12, 31)
        else:
            qe = date(y, qm + 1, 1) - timedelta(days=1)
        if qe <= t:
            out.append(qe.strftime("%Y%m%d"))
        qm -= 3
        if qm <= 0:
            qm, y = 12, y - 1
    return out


# ---------------------------------------------------------------- 公司基本信息

def upsert_company_info_all(*, force: bool = False) -> int:
    """全市场一次性拉取 stock_basic，批量写入 company_info。"""
    if not force:
        from fetcher import sync_status as ss
        if ss.synced_today("company_info"):
            log.info("company_info 今日已同步，跳过")
            return 0
    df = _call("stock_basic", exchange="", list_status="L",
               fields="ts_code,symbol,name,area,industry,market,list_date")
    if df is None or df.empty:
        return 0
    # 最新 daily_basic 取 PE/PB/市值（按 trade_date 全市场一次拉取）
    basics = {}
    try:
        # 取最近一个交易日的全市场 daily_basic
        cal = _call("trade_cal", exchange="SSE",
                    start_date=(date.today().replace(day=1)).strftime("%Y%m%d"),
                    end_date=date.today().strftime("%Y%m%d"),
                    fields="cal_date,is_open,pretrade_date")
        if cal is not None and not cal.empty:
            # is_open 可能是 int 1 或 str "1"，统一转 str 比较
            open_days = cal[cal["is_open"].astype(str) == "1"]
            if not open_days.empty:
                latest = open_days.iloc[-1]["cal_date"]
                db_df = _call(
                    "daily_basic", trade_date=latest,
                    fields="ts_code,pe,pb,total_mv,circ_mv,total_share,float_share")
                if db_df is not None and not db_df.empty:
                    for _, r in db_df.iterrows():
                        basics[str(r["ts_code"])] = r
    except Exception as exc:  # noqa: BLE001
        log.warning("daily_basic 拉取失败，PE/PB/市值留空：%s", exc)

    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            symbol = _plain(str(row["ts_code"]))
            if len(symbol) != 6:
                continue
            b = basics.get(str(row["ts_code"]))
            pe = _to_float(b["pe"]) if b is not None else None
            pb = _to_float(b["pb"]) if b is not None else None
            # 万元 -> 元
            mv = _to_float(b["total_mv"]) * 10000 if b is not None and _to_float(b["total_mv"]) else None
            cmv = _to_float(b["circ_mv"]) * 10000 if b is not None and _to_float(b["circ_mv"]) else None
            # 万股 -> 股
            ts = _to_float(b["total_share"]) * 10000 if b is not None and _to_float(b["total_share"]) else None
            fs = _to_float(b["float_share"]) * 10000 if b is not None and _to_float(b["float_share"]) else None
            cur.execute(
                """INSERT INTO company_info
                   (market, symbol, name, industry, pe, pb, market_cap,
                    circulating_cap, total_shares, circulating_shares, list_date, data)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol) DO UPDATE SET
                     name=EXCLUDED.name, industry=EXCLUDED.industry,
                     pe=EXCLUDED.pe, pb=EXCLUDED.pb,
                     market_cap=EXCLUDED.market_cap,
                     circulating_cap=EXCLUDED.circulating_cap,
                     total_shares=EXCLUDED.total_shares,
                     circulating_shares=EXCLUDED.circulating_shares,
                     list_date=EXCLUDED.list_date, data=EXCLUDED.data,
                     updated_at=now()""",
                (symbol, str(row.get("name") or ""), str(row.get("industry") or ""),
                 pe, pb, mv, cmv, ts, fs,
                 _to_date(row.get("list_date")), _row_json(row)))
            n += 1
    log.info("公司基本信息入库 %d 只（Tushare）", n)
    try:
        from fetcher import sync_status as ss
        ss.refresh_one("company_info")
    except Exception as exc:  # noqa: BLE001
        log.warning("刷新 company_info 水位失败：%s", exc)
    return n


# ---------------------------------------------------------------- 财务三表 + 指标（VIP 批量）

def _vip_periods(*, force: bool = False, tables: list | None = None) -> list:
    """近 2 年季度列表；非 force 时按 sync_status 水位裁掉已覆盖季度。"""
    periods = _periods()
    if force or not tables:
        return periods
    from fetcher import sync_status as ss
    floor = ss.min_latest(tables)
    if not floor:
        return periods
    kept = []
    for p in periods:
        d = _to_date(p)
        if d and d > floor:
            kept.append(p)
    if not kept:
        log.info("水位已覆盖至 %s，跳过 VIP（tables=%s）", floor, ",".join(tables))
    else:
        log.info("VIP 增量：水位 %s，待拉 %d/%d 季 %s",
                 floor, len(kept), len(periods), kept)
    return kept


def backfill_fin_statements_vip(*, force: bool = False) -> dict:
    """用 *_vip 接口按季度批量拉取三表 + 财务指标（8 个季度，约 32 次调用）。"""
    out = {"income": 0, "balance": 0, "cashflow": 0, "indicator": 0}
    pool = db.get_pool()
    fin_tables = ["fin_income", "fin_balance", "fin_cashflow", "fin_indicator"]
    periods = _vip_periods(force=force, tables=fin_tables)
    if not periods:
        out["skipped"] = True
        return out
    log.info("VIP 批量拉取 %d 个季度：%s", len(periods), periods)

    for period in periods:
        # 利润表
        try:
            df = _call("income_vip", period=period,
                       fields="ts_code,end_date,total_revenue,n_income_attr_p")
            if df is not None and not df.empty:
                with pool.connection() as conn, conn.cursor() as cur:
                    for _, row in df.iterrows():
                        symbol = _plain(str(row["ts_code"]))
                        if len(symbol) != 6:
                            continue
                        rd = _to_date(row.get("end_date"))
                        if not rd:
                            continue
                        cur.execute(
                            """INSERT INTO fin_income
                               (market, symbol, report_date, revenue, net_profit, data)
                               VALUES ('cn', %s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 revenue=EXCLUDED.revenue, net_profit=EXCLUDED.net_profit,
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd, _to_float(row.get("total_revenue")),
                             _to_float(row.get("n_income_attr_p")), _row_json(row)))
                        out["income"] += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("income_vip %s 失败：%s", period, exc)

        # 资产负债表
        try:
            df = _call("balancesheet_vip", period=period,
                       fields="ts_code,end_date,total_assets,total_liab,"
                              "total_hldr_eqy_exc_min_int")
            if df is not None and not df.empty:
                with pool.connection() as conn, conn.cursor() as cur:
                    for _, row in df.iterrows():
                        symbol = _plain(str(row["ts_code"]))
                        if len(symbol) != 6:
                            continue
                        rd = _to_date(row.get("end_date"))
                        if not rd:
                            continue
                        cur.execute(
                            """INSERT INTO fin_balance
                               (market, symbol, report_date, total_assets, total_liab,
                                equity, data)
                               VALUES ('cn', %s, %s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 total_assets=EXCLUDED.total_assets,
                                 total_liab=EXCLUDED.total_liab,
                                 equity=EXCLUDED.equity,
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd, _to_float(row.get("total_assets")),
                             _to_float(row.get("total_liab")),
                             _to_float(row.get("total_hldr_eqy_exc_min_int")),
                             _row_json(row)))
                        out["balance"] += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("balancesheet_vip %s 失败：%s", period, exc)

        # 现金流量表
        try:
            df = _call("cashflow_vip", period=period,
                       fields="ts_code,end_date")
            if df is not None and not df.empty:
                with pool.connection() as conn, conn.cursor() as cur:
                    for _, row in df.iterrows():
                        symbol = _plain(str(row["ts_code"]))
                        if len(symbol) != 6:
                            continue
                        rd = _to_date(row.get("end_date"))
                        if not rd:
                            continue
                        cur.execute(
                            """INSERT INTO fin_cashflow
                               (market, symbol, report_date, data)
                               VALUES ('cn', %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd, _row_json(row)))
                        out["cashflow"] += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("cashflow_vip %s 失败：%s", period, exc)

        # 财务指标
        try:
            df = _call("fina_indicator_vip", period=period,
                       fields="ts_code,end_date,roe,grossprofit_margin,"
                              "netprofit_margin")
            if df is not None and not df.empty:
                with pool.connection() as conn, conn.cursor() as cur:
                    for _, row in df.iterrows():
                        symbol = _plain(str(row["ts_code"]))
                        if len(symbol) != 6:
                            continue
                        rd = _to_date(row.get("end_date"))
                        if not rd:
                            continue
                        cur.execute(
                            """INSERT INTO fin_indicator
                               (market, symbol, report_date, roe, gross_margin,
                                net_margin, data)
                               VALUES ('cn', %s, %s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 roe=EXCLUDED.roe, gross_margin=EXCLUDED.gross_margin,
                                 net_margin=EXCLUDED.net_margin,
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd, _to_float(row.get("roe")),
                             _to_float(row.get("grossprofit_margin")),
                             _to_float(row.get("netprofit_margin")),
                             _row_json(row)))
                        out["indicator"] += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("fina_indicator_vip %s 失败：%s", period, exc)

        log.info("季度 %s 完成，累计 %s", period, out)
    try:
        from fetcher import sync_status as ss
        ss.refresh_tables(fin_tables)
    except Exception as exc:  # noqa: BLE001
        log.warning("刷新财务表水位失败：%s", exc)
    return out


def _upsert_fin_statements(symbol: str) -> dict:
    """单只股票的三表 + 财务指标（逐只接口，VIP 不可用时降级）。"""
    tsc = _ts_code(symbol)
    start = _cutoff().strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    out = {"income": 0, "balance": 0, "cashflow": 0, "indicator": 0}
    pool = db.get_pool()

    # 利润表
    try:
        df = _call("income", ts_code=tsc, start_date=start, end_date=end,
                   fields="ts_code,end_date,total_revenue,n_income_attr_p")
        if df is not None and not df.empty:
            with pool.connection() as conn, conn.cursor() as cur:
                for _, row in df.iterrows():
                    rd = _to_date(row.get("end_date"))
                    if not rd or rd < _cutoff():
                        continue
                    cur.execute(
                        """INSERT INTO fin_income
                           (market, symbol, report_date, revenue, net_profit, data)
                           VALUES ('cn', %s, %s, %s, %s, %s::jsonb)
                           ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                             revenue=EXCLUDED.revenue, net_profit=EXCLUDED.net_profit,
                             data=EXCLUDED.data, updated_at=now()""",
                        (symbol, rd, _to_float(row.get("total_revenue")),
                         _to_float(row.get("n_income_attr_p")), _row_json(row)))
                    out["income"] += 1
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] income 失败：%s", symbol, exc)

    # 资产负债表
    try:
        df = _call("balancesheet", ts_code=tsc, start_date=start, end_date=end,
                   fields="ts_code,end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int")
        if df is not None and not df.empty:
            with pool.connection() as conn, conn.cursor() as cur:
                for _, row in df.iterrows():
                    rd = _to_date(row.get("end_date"))
                    if not rd or rd < _cutoff():
                        continue
                    cur.execute(
                        """INSERT INTO fin_balance
                           (market, symbol, report_date, total_assets, total_liab,
                            equity, data)
                           VALUES ('cn', %s, %s, %s, %s, %s, %s::jsonb)
                           ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                             total_assets=EXCLUDED.total_assets,
                             total_liab=EXCLUDED.total_liab,
                             equity=EXCLUDED.equity,
                             data=EXCLUDED.data, updated_at=now()""",
                        (symbol, rd, _to_float(row.get("total_assets")),
                         _to_float(row.get("total_liab")),
                         _to_float(row.get("total_hldr_eqy_exc_min_int")),
                         _row_json(row)))
                    out["balance"] += 1
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] balancesheet 失败：%s", symbol, exc)

    # 现金流量表（只存原始 JSON）
    try:
        df = _call("cashflow", ts_code=tsc, start_date=start, end_date=end,
                   fields="ts_code,end_date")
        if df is not None and not df.empty:
            with pool.connection() as conn, conn.cursor() as cur:
                for _, row in df.iterrows():
                    rd = _to_date(row.get("end_date"))
                    if not rd or rd < _cutoff():
                        continue
                    cur.execute(
                        """INSERT INTO fin_cashflow
                           (market, symbol, report_date, data)
                           VALUES ('cn', %s, %s, %s::jsonb)
                           ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                             data=EXCLUDED.data, updated_at=now()""",
                        (symbol, rd, _row_json(row)))
                    out["cashflow"] += 1
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] cashflow 失败：%s", symbol, exc)

    # 财务指标
    try:
        df = _call("fina_indicator", ts_code=tsc, start_date=start, end_date=end,
                   fields="ts_code,end_date,roe,grossprofit_margin,netprofit_margin")
        if df is not None and not df.empty:
            with pool.connection() as conn, conn.cursor() as cur:
                for _, row in df.iterrows():
                    rd = _to_date(row.get("end_date"))
                    if not rd or rd < _cutoff():
                        continue
                    cur.execute(
                        """INSERT INTO fin_indicator
                           (market, symbol, report_date, roe, gross_margin,
                            net_margin, data)
                           VALUES ('cn', %s, %s, %s, %s, %s, %s::jsonb)
                           ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                             roe=EXCLUDED.roe, gross_margin=EXCLUDED.gross_margin,
                             net_margin=EXCLUDED.net_margin,
                             data=EXCLUDED.data, updated_at=now()""",
                        (symbol, rd, _to_float(row.get("roe")),
                         _to_float(row.get("grossprofit_margin")),
                         _to_float(row.get("netprofit_margin")),
                         _row_json(row)))
                    out["indicator"] += 1
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] fina_indicator 失败：%s", symbol, exc)

    return out


# ---------------------------------------------------------------- 十大股东

def _upsert_top_holders(symbol: str) -> int:
    tsc = _ts_code(symbol)
    start, end = _period_range()
    n = 0
    pool = db.get_pool()
    for holder_type, api in (("top10", "top10_holders"),
                             ("float10", "top10_floatholders")):
        try:
            df = _call(api, ts_code=tsc, start_date=start, end_date=end,
                       fields="ts_code,end_date,holder_name,hold_amount,hold_ratio")
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] %s 失败：%s", symbol, api, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            # 按报告期分组取前 10
            for rd_str, grp in df.groupby("end_date"):
                rd = _to_date(rd_str)
                if not rd or rd < _cutoff():
                    continue
                for i, (_, row) in enumerate(grp.iterrows(), start=1):
                    if i > 10:
                        break
                    name = str(row.get("holder_name") or "").strip()
                    if not name or name in ("--", "-"):
                        continue
                    cur.execute(
                        """INSERT INTO top_holders
                           (market, symbol, report_date, holder_type, rank,
                            holder_name, hold_shares, hold_ratio)
                           VALUES ('cn', %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (market, symbol, report_date, holder_type, rank)
                           DO UPDATE SET holder_name=EXCLUDED.holder_name,
                             hold_shares=EXCLUDED.hold_shares,
                             hold_ratio=EXCLUDED.hold_ratio""",
                        (symbol, rd, holder_type, i, name,
                         _to_float(row.get("hold_amount")) * 10000
                         if _to_float(row.get("hold_amount")) else None,
                         _to_float(row.get("hold_ratio"))))
                    n += 1
    return n


# ---------------------------------------------------------------- 股东人数

def _upsert_holder_number(symbol: str) -> int:
    tsc = _ts_code(symbol)
    start, end = _period_range()
    try:
        df = _call("stk_holdernumber", ts_code=tsc,
                   start_date=start, end_date=end,
                   fields="ts_code,end_date,holder_num")
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] stk_holdernumber 失败：%s", symbol, exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            rd = _to_date(row.get("end_date"))
            if not rd or rd < _cutoff():
                continue
            cnt = _to_float(row.get("holder_num"))
            cur.execute(
                """INSERT INTO holder_number
                   (market, symbol, report_date, holder_count, data)
                   VALUES ('cn', %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                     holder_count=EXCLUDED.holder_count,
                     data=EXCLUDED.data, updated_at=now()""",
                (symbol, rd, int(cnt) if cnt else None, _row_json(row)))
            n += 1
    return n


# ---------------------------------------------------------------- 股权质押

def _upsert_pledge(symbol: str) -> int:
    tsc = _ts_code(symbol)
    try:
        df = _call("pledge_stat", ts_code=tsc,
                   fields="ts_code,end_date,pledge_ratio")
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] pledge_stat 失败：%s", symbol, exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            rd = _to_date(row.get("end_date"))
            if not rd or rd < _cutoff():
                continue
            cur.execute(
                """INSERT INTO pledge_info
                   (market, symbol, stat_date, pledge_ratio, data)
                   VALUES ('cn', %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, stat_date) DO UPDATE SET
                     pledge_ratio=EXCLUDED.pledge_ratio,
                     data=EXCLUDED.data""",
                (symbol, rd, _to_float(row.get("pledge_ratio")), _row_json(row)))
            n += 1
    return n


# ---------------------------------------------------------------- 入口

_TYPE_CAT = {"P": "按产品", "D": "按地区", "I": "按行业"}


def backfill_main_business_vip(*, force: bool = False) -> int:
    """fina_mainbz_vip 按季度+类型批量，写入 main_business 与 fina_mainbz。

    约 8 季度 × 3 类型 × 分页，远快于东财逐只（~10s/只）。
    """
    periods = _vip_periods(
        force=force, tables=["main_business", "fina_mainbz"])
    if not periods:
        return 0
    total = 0
    pool = db.get_pool()
    log.info("fina_mainbz_vip 批量 %d 个季度 × 3 类型", len(periods))
    for period in periods:
        for bz_type, category in _TYPE_CAT.items():
            offset = 0
            while True:
                try:
                    df = _call(
                        "fina_mainbz_vip",
                        period=period,
                        type=bz_type,
                        offset=offset,
                        limit=8000,  # 显式分页大小，与下方的 n<8000 终止条件对齐
                        fields="ts_code,end_date,bz_item,bz_sales,bz_profit,"
                               "bz_cost,curr_type,update_flag",
                    )
                except Exception as exc:  # noqa: BLE001
                    # 部分中转站可能不支持 offset/type，降级无 offset
                    if offset == 0:
                        try:
                            df = _call(
                                "fina_mainbz_vip",
                                period=period,
                                type=bz_type,
                                limit=8000,
                                fields="ts_code,end_date,bz_item,bz_sales,"
                                       "bz_profit,bz_cost,curr_type,update_flag",
                            )
                        except Exception as exc2:  # noqa: BLE001
                            log.warning("fina_mainbz_vip %s/%s 失败：%s",
                                        period, bz_type, exc2)
                            break
                    else:
                        log.warning("fina_mainbz_vip %s/%s offset=%d 失败：%s",
                                    period, bz_type, offset, exc)
                        break
                if df is None or df.empty:
                    break
                rows_mb = []
                rows_fm = []
                for _, row in df.iterrows():
                    symbol = _plain(str(row["ts_code"]))
                    if len(symbol) != 6:
                        continue
                    ed = _to_date(row.get("end_date"))
                    if not ed or ed < _cutoff():
                        continue
                    item = str(row.get("bz_item") or "").strip()
                    if not item:
                        continue
                    sales = _to_float(row.get("bz_sales"))
                    profit = _to_float(row.get("bz_profit"))
                    rows_mb.append((symbol, ed, category, item, sales, None,
                                    profit, None))
                    rows_fm.append((
                        symbol, ed, item, sales, profit,
                        _to_float(row.get("bz_cost")),
                        str(row.get("curr_type") or ""),
                        str(row.get("update_flag") or ""),
                    ))
                if rows_mb:
                    with pool.connection() as conn, conn.cursor() as cur:
                        cur.executemany(
                            """INSERT INTO main_business
                               (market, symbol, report_date, category, item,
                                revenue, revenue_ratio, profit, profit_ratio)
                               VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (market, symbol, report_date,
                                            category, item) DO UPDATE SET
                                 revenue=EXCLUDED.revenue,
                                 profit=EXCLUDED.profit""",
                            rows_mb)
                        try:
                            cur.executemany(
                                """INSERT INTO fina_mainbz
                                   (market, symbol, end_date, bz_item, bz_sales,
                                    bz_profit, bz_cost, curr_type, update_flag)
                                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s)
                                   ON CONFLICT (market, symbol, end_date, bz_item)
                                   DO UPDATE SET bz_sales=EXCLUDED.bz_sales,
                                     bz_profit=EXCLUDED.bz_profit,
                                     bz_cost=EXCLUDED.bz_cost,
                                     update_flag=EXCLUDED.update_flag""",
                                rows_fm)
                        except Exception:
                            # fina_mainbz 表可能尚未建
                            pass
                    total += len(rows_mb)
                n = len(df)
                if n < 8000:
                    break
                offset += n
            log.info("fina_mainbz_vip %s/%s 累计 %d 行", period, bz_type, total)
    log.info("fina_mainbz_vip 完成：%d 行", total)
    try:
        from fetcher import sync_status as ss
        ss.refresh_tables(["main_business", "fina_mainbz"])
    except Exception as exc:  # noqa: BLE001
        log.warning("刷新主营构成水位失败：%s", exc)
    return total


def fetch_one(symbol: str, skip_fin: bool = False,
              skip_main_business: bool = False) -> dict:
    """抓取单只股票的全部基本面（近 2 年），返回各分类入库数。
    skip_fin=True 时跳过三表+指标（VIP 批量已拉过）。
    skip_main_business=True 时跳过东财主营构成（VIP 批量已拉过）。"""
    result = {"symbol": symbol}
    if not skip_fin:
        try:
            r = _upsert_fin_statements(symbol)
            result["fin_statements"] = r
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] 财务三表+指标失败：%s", symbol, exc)
            result["fin_statements"] = {}
    else:
        result["fin_statements"] = {"skipped": "vip_batch"}
    for name, fn in (("top_holders", _upsert_top_holders),
                     ("holder_number", _upsert_holder_number),
                     ("pledge", _upsert_pledge)):
        try:
            result[name] = fn(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] %s 失败：%s", symbol, name, exc)
            result[name] = 0
    if skip_main_business:
        result["main_business"] = {"skipped": "vip_batch"}
        return result
    # 仅 eastmoney 路径或 VIP 失败时走东财补充
    try:
        from fetcher.sources import cn_fundamentals as _cn
        try:
            result["main_business"] = _cn.upsert_main_business(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] 主营构成（东财补充）失败：%s", symbol, exc)
            result["main_business"] = 0
    except ImportError:
        result["main_business"] = 0
    return result


def check_token() -> dict:
    """校验 token 有效性与积分，返回 {ok, points}。"""
    try:
        df = _call("stock_basic", exchange="SSE", list_status="L",
                   fields="ts_code")
        n = 0 if df is None else len(df)
        return {"ok": True, "stocks": n}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
