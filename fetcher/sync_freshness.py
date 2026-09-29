"""同步任务新鲜度：判定哪些 job/表已拉过，可跳过。

供 backfill_* 与 audit 共用；规则与前端「数据更新」页一致。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fetcher.sync_registry import DAILY_COLS, JOB_TABLES, TABLE_BY_KEY, TABLES
from fetcher import sync_status as ss

log = logging.getLogger(__name__)

# 按交易日/公告日增量的任务（可用表级水位整段跳过）
DATE_BATCH_JOBS = {
    "daily_basic", "moneyflow", "dividend",
    "disclosure", "index", "hsgt_flow", "hsgt_top10", "margin",
    "top_list", "stk_limit", "block_trade", "adj_factor",
    "holdertrade", "daily_ts", "repurchase", "hk_hold",
}

# 按财报季度批量（用已结束季度判断，不用 ann_date）
QUARTER_BATCH_JOBS = {"forecast"}

# 一次性全市场（今天已同步且有数据则可跳过）
ONESHOT_JOBS = {
    "company_detail", "namechange", "new_share", "index_info",
}

# 逐只增量（内部已按 symbol max 跳过；表级最新日不能代表全市场）
PER_SYMBOL_JOBS = {
    "mainbz", "fina_audit", "managers", "share_float",
    "pledge_detail", "cyq_perf", "fundamentals",
}


def _latest_completed_quarter() -> Optional[date]:
    """最近一个已结束季度的季末日。"""
    try:
        from fetcher.sources.tushare_fundamentals import _periods, _to_date
        periods = _periods()
        if periods:
            return _to_date(periods[0])
    except Exception:  # noqa: BLE001
        pass
    today = date.today()
    qm = ((today.month - 1) // 3) * 3  # 上一季末月：3/6/9/12 的前一季
    if qm == 0:
        return date(today.year - 1, 12, 31)
    # qm 是当前季第一个月的前一个月所在… 简化：用季初减一天
    q_start_month = ((today.month - 1) // 3) * 3 + 1
    return date(today.year, q_start_month, 1) - timedelta(days=1)


def needs_update(date_col: Optional[str], latest, rows: int) -> bool:
    today = date.today()
    if latest is None:
        return rows == 0
    if rows == 0:
        return True
    if date_col is None:
        return False
    if date_col in DAILY_COLS:
        return latest < today
    # 季报类：覆盖到最近已结束季度即视为新鲜（Q3 中有 Q2 数据不算落后）
    q_latest = _latest_completed_quarter()
    if q_latest is not None:
        return latest < q_latest
    qm = ((today.month - 1) // 3) * 3 + 1
    quarter_start = date(today.year, qm, 1)
    return latest < quarter_start


def table_status(table: str) -> dict:
    """单表状态：是否需更新 + 原因。"""
    meta = TABLE_BY_KEY.get(table, {})
    dc = meta.get("date_col")
    wm = ss.get_row(table)
    if wm is None:
        return {
            "table": table, "name": meta.get("name", table),
            "group": meta.get("group", ""),
            "rows": 0, "latest_date": None, "last_synced_at": None,
            "needs_update": True, "reason": "无水位（请先 refresh_sync_status）",
        }
    rows = int(wm.get("row_count") or 0)
    latest = wm.get("latest_date")
    last_synced = wm.get("last_synced_at")
    if rows == 0:
        needs, reason = True, "无数据"
    elif dc is None:
        # 无日期列：当日已同步则视为新鲜
        if ss.synced_today(table):
            needs, reason = False, "今日已同步"
        else:
            needs, reason = True, "无日期列且非今日同步"
    elif needs_update(dc, latest, rows):
        needs, reason = True, f"最新 {latest} 落后"
    else:
        needs, reason = False, "已覆盖到最新"
    return {
        "table": table, "name": meta.get("name", table),
        "group": meta.get("group", ""),
        "rows": rows,
        "latest_date": latest.isoformat() if latest else None,
        "last_synced_at": (
            last_synced.isoformat(timespec="seconds") if last_synced else None
        ),
        "needs_update": needs, "reason": reason,
    }


def job_status(job: str) -> dict:
    """回填任务（--only 名）状态。"""
    tables = JOB_TABLES.get(job) or []
    parts = [table_status(t) for t in tables]
    if not parts:
        return {
            "job": job, "tables": [], "needs_update": True,
            "skip_ok": False, "reason": "未知任务",
        }
    if job in PER_SYMBOL_JOBS:
        # 不能整段跳过；仍报告子表状态
        any_need = any(p["needs_update"] for p in parts)
        return {
            "job": job, "tables": parts,
            "needs_update": any_need,
            "skip_ok": False,
            "reason": "逐只增量（内部跳过已有股票，任务仍会启动）",
        }
    if job in ONESHOT_JOBS:
        # 所有子表今日同步且有数据 → 可跳过
        all_today = all(p["rows"] > 0 and ss.synced_today(p["table"]) for p in parts)
        return {
            "job": job, "tables": parts,
            "needs_update": not all_today,
            "skip_ok": all_today,
            "reason": "今日已同步，跳过" if all_today else "一次性任务待跑",
        }
    if job in QUARTER_BATCH_JOBS:
        q = _latest_completed_quarter()
        # 用子表 latest 与最新已结束季度比（忽略 ann_date 日更规则）
        behind = []
        for p in parts:
            if p["rows"] == 0:
                behind.append(p["table"])
                continue
            ld = p["latest_date"]
            if not ld or (q and date.fromisoformat(ld) < q):
                behind.append(p["table"])
        any_need = bool(behind)
        return {
            "job": job, "tables": parts,
            "needs_update": any_need,
            "skip_ok": not any_need,
            "reason": (
                "水位已新，跳过" if not any_need
                else f"季度落后：{','.join(behind)}"
            ),
        }
    # 日期批量：任一「有意义」子表需更新则跑
    # suspend 允许长期为空，不单独拖累 moneyflow 任务
    meaningful = [p for p in parts if not (
        p["table"] == "suspend" and p["rows"] == 0)]
    check = meaningful or parts
    any_need = any(p["needs_update"] for p in check)
    return {
        "job": job, "tables": parts,
        "needs_update": any_need,
        "skip_ok": not any_need,
        "reason": "水位已新，跳过" if not any_need else "存在落后表，需增量",
    }


def should_skip_job(job: str, *, force: bool = False) -> tuple[bool, str]:
    """是否跳过该回填任务。返回 (skip, reason)。"""
    if force:
        return False, "force"
    st = job_status(job)
    if st.get("skip_ok"):
        return True, st.get("reason") or "已新鲜"
    return False, st.get("reason") or "需更新"


def audit_report(*, jobs: list[str] | None = None) -> list[dict]:
    """生成任务审计列表。"""
    names = jobs or sorted(JOB_TABLES.keys())
    return [job_status(j) for j in names]


def format_audit(rows: list[dict]) -> str:
    lines = []
    lines.append(f"{'任务':<16} {'动作':<8} {'说明'}")
    lines.append("-" * 72)
    for r in rows:
        action = "跳过" if r.get("skip_ok") else (
            "内部增量" if r["job"] in PER_SYMBOL_JOBS else "需拉取"
        )
        lines.append(f"{r['job']:<16} {action:<8} {r.get('reason', '')}")
        for t in r.get("tables") or []:
            flag = "缺" if t["needs_update"] else "齐"
            lines.append(
                f"  [{flag}] {t['table']:<20} rows={t['rows']:<10} "
                f"latest={t['latest_date'] or '-':<12} {t['reason']}"
            )
    return "\n".join(lines)


# 向后兼容别名
_needs_update = needs_update
