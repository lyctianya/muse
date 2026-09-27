"""策略选股器：字段元数据 + 条件筛选执行。

GET  /api/screener/fields  字段元数据（供前端渲染条件构造器）
POST /api/screener/run     按条件筛选 A 股（market='cn'）

有 db_col 的字段走 SQL WHERE（daily_basic 列）；
db_col 为空的是 K 线形态字段，在 Python 层按 symbol 分组计算后过滤。
"""
import logging
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import _conn

log = logging.getLogger(__name__)
router = APIRouter()

# 字段元数据：key / label / unit / 允许的运算符 / daily_basic 列(None=形态计算) / 换算倍数
FIELDS = [
    {"key": "total_mv", "label": "总市值", "unit": "亿元",
     "ops": ["between", "gt", "lt"], "db_col": "total_mv", "scale": 1e8},
    {"key": "circ_mv", "label": "流通市值", "unit": "亿元",
     "ops": ["between", "gt", "lt"], "db_col": "circ_mv", "scale": 1e8},
    {"key": "pe_ttm", "label": "市盈率TTM", "unit": "倍",
     "ops": ["lt", "gt", "between"], "db_col": "pe_ttm"},
    {"key": "pb", "label": "市净率", "unit": "倍",
     "ops": ["lt", "gt", "between"], "db_col": "pb"},
    {"key": "dv_ratio", "label": "股息率", "unit": "%",
     "ops": ["gt", "lt", "between"], "db_col": "dv_ratio"},
    {"key": "turnover_rate", "label": "换手率", "unit": "%",
     "ops": ["gt", "lt", "between"], "db_col": "turnover_rate"},
    {"key": "pct_change", "label": "最新涨跌幅", "unit": "%",
     "ops": ["gt", "lt", "between"], "db_col": None},
    {"key": "consec_up", "label": "连涨天数", "unit": "天",
     "ops": ["gte", "lte"], "db_col": None},
    {"key": "consec_down", "label": "连跌天数", "unit": "天",
     "ops": ["gte", "lte"], "db_col": None},
    {"key": "week_up_streak", "label": "周线连涨", "unit": "周",
     "ops": ["gte"], "db_col": None},
    {"key": "week_down_streak", "label": "周线连跌", "unit": "周",
     "ops": ["gte"], "db_col": None},
    {"key": "rebound60", "label": "60日底部反弹", "unit": "%",
     "ops": ["gte", "lte"], "db_col": None},
]
FIELD_MAP = {f["key"]: f for f in FIELDS}

# SQL 运算符映射
SQL_OPS = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "between": "BETWEEN"}


@router.get("/api/screener/fields")
def screener_fields():
    """字段元数据：key/label/unit/ops/db_col/scale。"""
    return FIELDS


class FilterItem(BaseModel):
    key: str
    op: str
    value: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None


class RunBody(BaseModel):
    filters: list = []
    limit: int = 200


def _check_filter(f: FilterItem) -> dict:
    """校验单个条件，返回字段元数据；非法抛 400。"""
    meta = FIELD_MAP.get(f.key)
    if meta is None:
        raise HTTPException(status_code=400, detail=f"未知字段: {f.key}")
    if f.op not in SQL_OPS:
        raise HTTPException(status_code=400, detail=f"未知运算符: {f.op}")
    if f.op not in meta["ops"]:
        raise HTTPException(status_code=400,
                            detail=f"字段 {f.key} 不支持运算符 {f.op}")
    if f.op == "between":
        if f.min is None or f.max is None:
            raise HTTPException(status_code=400,
                                detail=f"字段 {f.key} between 需要 min/max")
    elif f.value is None:
        raise HTTPException(status_code=400,
                            detail=f"字段 {f.key} 需要 value")
    return meta


def _match_py(op: str, v: Any, f: FilterItem) -> bool:
    """Python 层形态条件匹配。"""
    if v is None:
        return False
    if op == "between":
        return f.min <= v <= f.max
    if op == "gt":
        return v > f.value
    if op == "lt":
        return v < f.value
    if op == "gte":
        return v >= f.value
    if op == "lte":
        return v <= f.value
    return False


def _calc_features(bars: list) -> dict:
    """按 symbol 分组计算形态特征。

    bars: [(trade_date, close, low, pct_change)] 按日期升序。
    """
    n = len(bars)
    if n == 0:
        return {"consec_up": 0, "consec_down": 0, "pct_change": None,
                "week_up_streak": 0, "week_down_streak": 0, "rebound60": None,
                "close": None}

    latest = bars[-1]
    close = latest[1]

    # 连涨 / 连跌：从最近一日往前数
    consec_up = consec_down = 0
    for _, _, _, pc in reversed(bars):
        if pc is None:
            break
        if pc > 0 and consec_down == 0:
            consec_up += 1
        elif pc < 0 and consec_up == 0:
            consec_down += 1
        else:
            break

    # 周线：按自然周取每周最后一个交易日收盘价
    weeks = []  # [(week_key, last_close)] 升序
    cur_key, cur_close = None, None
    for d, c, _, _ in bars:
        if c is None:
            continue
        wk = (d.isocalendar()[0], d.isocalendar()[1])
        if wk != cur_key:
            if cur_key is not None:
                weeks.append((cur_key, cur_close))
            cur_key, cur_close = wk, c
        else:
            cur_close = c
    if cur_key is not None:
        weeks.append((cur_key, cur_close))

    # 最近一周若未包含周五（非完整周），剔除
    if weeks and latest[0].weekday() < 4:
        weeks.pop()

    week_up_streak = week_down_streak = 0
    for i in range(len(weeks) - 1, 0, -1):
        prev, cur = weeks[i - 1][1], weeks[i][1]
        if cur is None or prev is None or prev == 0:
            break
        if cur > prev and week_down_streak == 0:
            week_up_streak += 1
        elif cur < prev and week_up_streak == 0:
            week_down_streak += 1
        else:
            break

    # 60 日底部反弹
    window = bars[-60:]
    lows = [b[2] for b in window if b[2]]
    rebound60 = None
    if lows and close:
        m = min(lows)
        if m > 0:
            rebound60 = round((close - m) / m * 100, 2)

    return {
        "consec_up": consec_up,
        "consec_down": consec_down,
        "pct_change": latest[3],
        "week_up_streak": week_up_streak,
        "week_down_streak": week_down_streak,
        "rebound60": rebound60,
        "close": close,
    }


@router.post("/api/screener/run")
def screener_run(body: RunBody):
    """执行选股：SQL 条件先筛候选，形态条件 Python 层过滤。"""
    filters = [FilterItem(**f) if isinstance(f, dict) else f
               for f in (body.filters or [])]
    metas = [_check_filter(f) for f in filters]
    limit = max(1, min(body.limit or 200, 1000))

    sql_filters = [(f, m) for f, m in zip(filters, metas) if m["db_col"]]
    py_filters = [(f, m) for f, m in zip(filters, metas) if not m["db_col"]]

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(trade_date) FROM daily_basic WHERE market = 'cn'")
            latest = cur.fetchone()[0]
            use_basic = latest is not None

            if not use_basic:
                # daily_basic 为空：退化为全量现役 A 股
                cur.execute(
                    "SELECT market, trade_date FROM daily_bars"
                    " WHERE market = 'cn' ORDER BY trade_date DESC LIMIT 1")
                r = cur.fetchone()
                latest = r[1] if r else None
                base_sql = (
                    "SELECT s.symbol, s.name, NULL, NULL, NULL, NULL,"
                    " NULL, NULL, b.close, b.pct_change"
                    " FROM symbols s"
                    " LEFT JOIN daily_bars b ON b.market = 'cn'"
                    " AND b.symbol = s.symbol AND b.trade_date = %s"
                    " WHERE s.market = 'cn' AND s.active = TRUE"
                )
                base_params: list = [latest] if latest else []
                if latest is None:
                    # 连 daily_bars 也没有：只返回代码名称
                    base_sql = ("SELECT symbol, name, NULL, NULL, NULL, NULL,"
                                " NULL, NULL, NULL, NULL FROM symbols"
                                " WHERE market = 'cn' AND active = TRUE")
                    base_params = []
            else:
                base_sql = (
                    "SELECT d.symbol, s.name, d.total_mv, d.circ_mv,"
                    " d.pe_ttm, d.pb, d.dv_ratio, d.turnover_rate,"
                    " b.close, b.pct_change"
                    " FROM daily_basic d"
                    " JOIN symbols s ON s.market = 'cn'"
                    " AND s.symbol = d.symbol AND s.active = TRUE"
                    " LEFT JOIN daily_bars b ON b.market = 'cn'"
                    " AND b.symbol = d.symbol AND b.trade_date = %s"
                    " WHERE d.market = 'cn' AND d.trade_date = %s"
                )
                base_params = [latest, latest]

            # 拼 SQL 条件（total_mv/circ_mv 按 scale 换算：亿元 -> 元）
            if not use_basic and sql_filters:
                raise HTTPException(
                    status_code=400,
                    detail="daily_basic 暂无数据，无法按基本面字段筛选，"
                           "请先回填 daily_basic")
            for f, m in sql_filters:
                col = m["db_col"]
                scale = m.get("scale") or 1
                if f.op == "between":
                    base_sql += f" AND d.{col} BETWEEN %s AND %s"
                    base_params += [f.min * scale, f.max * scale]
                else:
                    base_sql += f" AND d.{col} {SQL_OPS[f.op]} %s"
                    base_params.append(f.value * scale)
            base_sql += " ORDER BY d.symbol" if use_basic else " ORDER BY s.symbol"

            cur.execute(base_sql, base_params)
            cands = cur.fetchall()

            # 形态计算需要的 bars（近 ~90 个交易日，按 130 自然日兜底）
            need_bars = bool(py_filters)
            feats: dict = {}
            if need_bars and latest and cands:
                cutoff = latest - timedelta(days=130)
                symbols = [r[0] for r in cands]
                bar_rows: dict = {}
                for i in range(0, len(symbols), 1000):
                    batch = symbols[i:i + 1000]
                    cur.execute(
                        "SELECT symbol, trade_date, close, low, pct_change"
                        " FROM daily_bars WHERE market = 'cn'"
                        " AND symbol = ANY(%s) AND trade_date > %s"
                        " ORDER BY symbol, trade_date",
                        (batch, cutoff))
                    for sym, d, c, lo, pc in cur.fetchall():
                        bar_rows.setdefault(sym, []).append((d, c, lo, pc))
                for sym, bars in bar_rows.items():
                    feats[sym] = _calc_features(bars)

    rows = []
    for r in cands:
        sym = r[0]
        feat = feats.get(sym) if need_bars else None

        # Python 层过滤形态条件
        ok = True
        for f, m in py_filters:
            v = (feat or {}).get(f.key)
            if not _match_py(f.op, v, f):
                ok = False
                break
        if not ok:
            continue

        total_mv = r[2]
        rows.append({
            "symbol": sym,
            "name": r[1],
            "close": round(r[8], 2) if r[8] is not None else None,
            "pct_change": round(r[9], 2) if r[9] is not None else None,
            "total_mv_yi": round(total_mv / 1e8, 2)
            if total_mv is not None else None,
            "pe_ttm": round(r[4], 2) if r[4] is not None else None,
            "consec_up": (feat or {}).get("consec_up", 0),
            "consec_down": (feat or {}).get("consec_down", 0),
            "week_up_streak": (feat or {}).get("week_up_streak", 0),
            "week_down_streak": (feat or {}).get("week_down_streak", 0),
            "rebound60": (feat or {}).get("rebound60"),
        })

    return {"total": len(rows), "rows": rows[:limit]}
