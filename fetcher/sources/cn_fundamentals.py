"""A股基本面数据：AkShare（第一期仅 A股，近 2 年）。

覆盖：
- 公司基本信息 stock_individual_info_em（含行业/PE/PB/市值）
- 财务三表 stock_*_sheet_by_report_em（利润表/资产负债表/现金流量表）
- 财务指标 stock_financial_analysis_indicator
- 主营业务构成 stock_zygc_em
- 前十大股东 stock_gdfx_top_10_em / 前十大流通股东 stock_gdfx_free_top_10_em
- 股权质押 stock_gpzy_pledge_ratio_em
- 股东人数 stock_zh_a_gdhs_detail_em
- 股东增减持 stock_ggcg_em

所有写入均为幂等 upsert，重跑安全。
"""
import json
import logging
import re
from datetime import date, timedelta
from typing import Optional

import akshare as ak
import pandas as pd

from fetcher import db
from fetcher.sources import _util

log = logging.getLogger(__name__)
MARKET = "cn"

# 近 2 年
YEARS = 2


def _cutoff() -> date:
    return date.today() - timedelta(days=365 * YEARS + 5)


def _em_symbol(symbol: str, lower: bool = False) -> str:
    """6位代码 -> 东方财富格式：SH600519 / sh600519。"""
    s = symbol.strip().zfill(6)
    if s.startswith("6"):
        prefix = "SH"
    elif s.startswith(("4", "8")):
        prefix = "BJ"
    else:
        prefix = "SZ"
    return (prefix + s).lower() if lower else (prefix + s)


def _to_date(v) -> Optional[date]:
    """尽力把各种日期格式转成 date，失败返回 None。"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(v) -> Optional[float]:
    """尽力转 float：处理 '--'、'%'、逗号、'万/亿'单位。"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace(",", "")
    if s in ("", "--", "-", "nan", "None"):
        return None
    mult = 1.0
    if s.endswith("%"):
        s = s[:-1]
    elif s.endswith("亿"):
        s, mult = s[:-1], 1e8
    elif s.endswith("万"):
        s, mult = s[:-1], 1e4
    try:
        return float(s) * mult
    except ValueError:
        return None


def _pick(row: pd.Series, *names: str):
    """按多个候选列名取值，列名不存在则返回 None。"""
    for n in names:
        if n in row.index:
            return row[n]
    return None


def _row_json(row: pd.Series) -> str:
    return json.dumps({str(k): (None if pd.isna(v) else str(v))
                       for k, v in row.items()}, ensure_ascii=False)


# ---------------------------------------------------------------- 公司基本信息

@_util.retry("公司基本信息")
def _fetch_company_info(symbol: str) -> Optional[dict]:
    df = ak.stock_individual_info_em(symbol=symbol)
    if df is None or df.empty:
        return None
    # 纵表：列为 [项目, 值] 或 [item, value]
    cols = list(df.columns)
    k_col, v_col = cols[0], cols[1]
    info = {str(r[k_col]).strip(): str(r[v_col]).strip() for _, r in df.iterrows()}

    def get(*keys):
        for k in keys:
            if k in info and info[k] not in ("", "--", "-"):
                return info[k]
        return None

    return {
        "name": get("股票简称"),
        "industry": get("行业", "所属行业"),
        "pe": _to_float(get("市盈率-动态", "市盈率")),
        "pb": _to_float(get("市净率")),
        "market_cap": _to_float(get("总市值")),
        "circulating_cap": _to_float(get("流通市值")),
        "total_shares": _to_float(get("总股本")),
        "circulating_shares": _to_float(get("流通股")),
        "list_date": _to_date(get("上市时间", "上市日期")),
        "data": json.dumps(info, ensure_ascii=False),
    }


def upsert_company_info(symbol: str) -> bool:
    info = _fetch_company_info(symbol)
    if not info:
        return False
    pool = db.get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
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
            (symbol, info["name"], info["industry"], info["pe"], info["pb"],
             info["market_cap"], info["circulating_cap"], info["total_shares"],
             info["circulating_shares"], info["list_date"], info["data"]),
        )
    return True


# ---------------------------------------------------------------- 财务三表

def _fetch_report(symbol: str, kind: str) -> pd.DataFrame:
    """kind: income | balance | cashflow。返回原始 DataFrame（可能为空）。"""
    em = _em_symbol(symbol)
    fn = {
        "income": ak.stock_profit_sheet_by_report_em,
        "balance": ak.stock_balance_sheet_by_report_em,
        "cashflow": ak.stock_cash_flow_sheet_by_report_em,
    }[kind]
    return fn(symbol=em)


def _report_date(row: pd.Series) -> Optional[date]:
    d = _to_date(_pick(row, "报告期", "REPORT_DATE", "报告日期"))
    if d and d >= _cutoff():
        return d
    return None


def upsert_fin_statements(symbol: str) -> dict:
    """抓取三表并入库，返回 {income: n, balance: n, cashflow: n}。"""
    out = {}
    pool = db.get_pool()
    specs = {
        "income": ("fin_income",
                   ("营业收入", "营业总收入", "REVENUE"),
                   ("净利润", "归母净利润", "NET_PROFIT")),
        "balance": ("fin_balance",
                    ("资产总计", "TOTAL_ASSETS"),
                    ("负债合计", "TOTAL_LIAB")),
        "cashflow": ("fin_cashflow", (), ()),
    }
    for kind, (table, rev_keys, profit_keys) in specs.items():
        try:
            df = _fetch_report(symbol, kind)
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] %s 拉取失败：%s", symbol, kind, exc)
            out[kind] = 0
            continue
        n = 0
        if df is not None and not df.empty:
            with pool.connection() as conn, conn.cursor() as cur:
                for _, row in df.iterrows():
                    rd = _report_date(row)
                    if not rd:
                        continue
                    if kind == "income":
                        cur.execute(
                            """INSERT INTO fin_income
                               (market, symbol, report_date, revenue, net_profit, data)
                               VALUES ('cn', %s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 revenue=EXCLUDED.revenue, net_profit=EXCLUDED.net_profit,
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd,
                             _to_float(_pick(row, *rev_keys)),
                             _to_float(_pick(row, *profit_keys)),
                             _row_json(row)))
                    elif kind == "balance":
                        cur.execute(
                            """INSERT INTO fin_balance
                               (market, symbol, report_date, total_assets, total_liab, data)
                               VALUES ('cn', %s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 total_assets=EXCLUDED.total_assets,
                                 total_liab=EXCLUDED.total_liab,
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd,
                             _to_float(_pick(row, *rev_keys)),
                             _to_float(_pick(row, *profit_keys)),
                             _row_json(row)))
                    else:
                        cur.execute(
                            """INSERT INTO fin_cashflow
                               (market, symbol, report_date, data)
                               VALUES ('cn', %s, %s, %s::jsonb)
                               ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                                 data=EXCLUDED.data, updated_at=now()""",
                            (symbol, rd, _row_json(row)))
                    n += 1
        out[kind] = n
        log.info("[%s] %s 入库 %d 期", symbol, kind, n)
    return out


# ---------------------------------------------------------------- 财务指标

@_util.retry("财务指标")
def upsert_fin_indicator(symbol: str) -> int:
    df = ak.stock_financial_analysis_indicator(symbol=symbol)
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            rd = _to_date(_pick(row, "日期", "报告期"))
            if not rd or rd < _cutoff():
                continue
            cur.execute(
                """INSERT INTO fin_indicator
                   (market, symbol, report_date, roe, gross_margin, net_margin, data)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                     roe=EXCLUDED.roe, gross_margin=EXCLUDED.gross_margin,
                     net_margin=EXCLUDED.net_margin,
                     data=EXCLUDED.data, updated_at=now()""",
                (symbol, rd,
                 _to_float(_pick(row, "净资产收益率", "ROE", "净资产收益率(加权)")),
                 _to_float(_pick(row, "毛利率", "销售毛利率")),
                 _to_float(_pick(row, "净利率", "销售净利率")),
                 _row_json(row)))
            n += 1
    log.info("[%s] 财务指标入库 %d 期", symbol, n)
    return n


# ---------------------------------------------------------------- 主营业务构成

@_util.retry("主营业务构成")
def upsert_main_business(symbol: str) -> int:
    df = ak.stock_zygc_em(symbol=_em_symbol(symbol))
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            rd = _to_date(_pick(row, "报告日期", "报告期"))
            if not rd or rd < _cutoff():
                continue
            category = str(_pick(row, "分类类型", "分类", "类型") or "")
            item = str(_pick(row, "主营构成", "项目", "名称", "分项") or "")
            if not item:
                continue
            cur.execute(
                """INSERT INTO main_business
                   (market, symbol, report_date, category, item,
                    revenue, revenue_ratio, profit, profit_ratio)
                   VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (market, symbol, report_date, category, item)
                   DO UPDATE SET revenue=EXCLUDED.revenue,
                     revenue_ratio=EXCLUDED.revenue_ratio,
                     profit=EXCLUDED.profit, profit_ratio=EXCLUDED.profit_ratio""",
                (symbol, rd, category, item,
                 _to_float(_pick(row, "主营收入", "营业收入", "收入")),
                 _to_float(_pick(row, "收入比例", "收入占比")),
                 _to_float(_pick(row, "主营利润", "营业利润", "利润")),
                 _to_float(_pick(row, "利润比例", "利润占比"))))
            n += 1
    log.info("[%s] 主营构成入库 %d 条", symbol, n)
    return n


# ---------------------------------------------------------------- 十大股东

def _quarter_ends() -> list:
    """近 2 年的季度末（YYYYMMDD），用于十大股东按季度拉取。"""
    today = date.today()
    out = []
    y, m = today.year, today.month
    # 当前季度往前推 8 个季度
    q = (m - 1) // 3
    for _ in range(8):
        q_end_month = q * 3 + 3
        q_end_day = {3: 31, 6: 30, 9: 30, 12: 31}[q_end_month]
        out.append(date(y, q_end_month, q_end_day))
        q -= 1
        if q < 0:
            q, y = 3, y - 1
    # 过滤未来日期（如本季度末还没到），否则接口返回空导致 akshare 解析报错
    return [d for d in out if _cutoff() <= d <= today]


@_util.retry("十大股东")
def upsert_top_holders(symbol: str) -> int:
    em = _em_symbol(symbol, lower=True)
    pool = db.get_pool()
    n = 0
    for qd in _quarter_ends():
        qstr = qd.strftime("%Y%m%d")
        for holder_type, fn in (("top10", ak.stock_gdfx_top_10_em),
                                ("float10", ak.stock_gdfx_free_top_10_em)):
            try:
                df = fn(symbol=em, date=qstr)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] %s %s 拉取失败：%s", symbol, holder_type, qstr, exc)
                continue
            if df is None or df.empty:
                continue
            with pool.connection() as conn, conn.cursor() as cur:
                for i, (_, row) in enumerate(df.iterrows(), start=1):
                    if i > 10:
                        break
                    name = str(_pick(row, "股东名称", "名称") or "")
                    if not name or name in ("--", "-"):
                        continue
                    cur.execute(
                        """INSERT INTO top_holders
                           (market, symbol, report_date, holder_type, rank,
                            holder_name, hold_shares, hold_ratio, change)
                           VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (market, symbol, report_date, holder_type, rank)
                           DO UPDATE SET holder_name=EXCLUDED.holder_name,
                             hold_shares=EXCLUDED.hold_shares,
                             hold_ratio=EXCLUDED.hold_ratio, change=EXCLUDED.change""",
                        (symbol, qd, holder_type, i, name,
                         _to_float(_pick(row, "持股数量", "持股数")),
                         _to_float(_pick(row, "持股比例", "占总股本比例")),
                         _to_float(_pick(row, "增减", "变动"))))
                    n += 1
    log.info("[%s] 十大股东入库 %d 条", symbol, n)
    return n


# ---------------------------------------------------------------- 股东人数

@_util.retry("股东人数")
def upsert_holder_number(symbol: str) -> int:
    df = ak.stock_zh_a_gdhs_detail_em(symbol=symbol)
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            rd = _to_date(_pick(row, "股东户数统计截止日", "统计日期", "日期", "报告期"))
            if not rd or rd < _cutoff():
                continue
            cnt = _to_float(_pick(row, "股东户数-本次", "股东人数", "股东户数", "户数"))
            cur.execute(
                """INSERT INTO holder_number
                   (market, symbol, report_date, holder_count, avg_shares, data)
                   VALUES ('cn', %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, report_date) DO UPDATE SET
                     holder_count=EXCLUDED.holder_count,
                     avg_shares=EXCLUDED.avg_shares,
                     data=EXCLUDED.data, updated_at=now()""",
                (symbol, rd,
                 int(cnt) if cnt else None,
                 _to_float(_pick(row, "户均持股数量", "户均持股", "平均持股")),
                 _row_json(row)))
            n += 1
    log.info("[%s] 股东人数入库 %d 期", symbol, n)
    return n


# ---------------------------------------------------------------- 全市场维度：质押 / 增减持

@_util.retry("股权质押")
def upsert_pledge_all(stat_date: Optional[date] = None) -> int:
    """全市场质押比例快照。stat_date 缺省为今天。"""
    d = stat_date or date.today()
    try:
        df = ak.stock_gpzy_pledge_ratio_em(date=d.strftime("%Y%m%d"))
    except TypeError as exc:
        # akshare 内部解析异常（如 result 为 None），重试无意义，直接跳过
        log.warning("股权质押接口返回异常（%s），跳过本轮", exc)
        return 0
    if df is None or df.empty:
        return 0
    pool = db.get_pool()
    n = 0
    with pool.connection() as conn, conn.cursor() as cur:
        for _, row in df.iterrows():
            code = re.sub(r"\D", "", str(_pick(row, "股票代码", "代码") or ""))
            if len(code) != 6:
                continue
            cur.execute(
                """INSERT INTO pledge_info
                   (market, symbol, stat_date, pledge_ratio, pledged_shares, data)
                   VALUES ('cn', %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (market, symbol, stat_date) DO UPDATE SET
                     pledge_ratio=EXCLUDED.pledge_ratio,
                     pledged_shares=EXCLUDED.pledged_shares,
                     data=EXCLUDED.data, updated_at=now()""",
                (code, d,
                 _to_float(_pick(row, "质押比例", "质押占总股本比例")),
                 _to_float(_pick(row, "质押股数", "质押数量")),
                 _row_json(row)))
            n += 1
    log.info("股权质押入库 %d 条（%s）", n, d)
    return n


@_util.retry("股东增减持")
def upsert_holder_trade_all() -> int:
    """全市场股东增持/减持（近 2 年过滤）。"""
    pool = db.get_pool()
    n = 0
    for trade_type, param in (("增持", "股东增持"), ("减持", "股东减持")):
        try:
            df = ak.stock_ggcg_em(symbol=param)
        except Exception as exc:  # noqa: BLE001
            log.warning("股东%s拉取失败：%s", trade_type, exc)
            continue
        if df is None or df.empty:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            for _, row in df.iterrows():
                td = _to_date(_pick(row, "变动日期", "公告日期", "日期"))
                if not td or td < _cutoff():
                    continue
                code = re.sub(r"\D", "", str(_pick(row, "股票代码", "代码") or ""))
                if len(code) != 6:
                    continue
                cur.execute(
                    """INSERT INTO holder_trade
                       (market, symbol, holder_name, trade_type, trade_date,
                        shares, price, amount, ratio, data)
                       VALUES ('cn', %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                       ON CONFLICT (market, symbol, holder_name, trade_type,
                                    trade_date, shares) DO NOTHING""",
                    (code,
                     str(_pick(row, "股东名称", "变动股东", "名称") or ""),
                     trade_type, td,
                     _to_float(_pick(row, "变动股数", "增减股数", "变动数量")),
                     _to_float(_pick(row, "成交均价", "均价", "价格")),
                     _to_float(_pick(row, "变动金额", "金额")),
                     _to_float(_pick(row, "变动比例", "占总股本比例")),
                     _row_json(row)))
                n += 1
    log.info("股东增减持入库 %d 条", n)
    return n


# ---------------------------------------------------------------- 单只股票全量

def fetch_one(symbol: str) -> dict:
    """抓取单只股票的全部基本面（近 2 年），返回各分类入库数。"""
    result = {"symbol": symbol}
    try:
        result["company_info"] = 1 if upsert_company_info(symbol) else 0
    except Exception as exc:  # noqa: BLE001
        log.warning("[%s] 基本信息失败：%s", symbol, exc)
        result["company_info"] = 0
    for name, fn in (("fin_statements", upsert_fin_statements),
                     ("fin_indicator", upsert_fin_indicator),
                     ("main_business", upsert_main_business),
                     ("top_holders", upsert_top_holders),
                     ("holder_number", upsert_holder_number)):
        try:
            result[name] = fn(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] %s 失败：%s", symbol, name, exc)
            result[name] = 0
    return result
