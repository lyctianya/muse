"""数据同步管理：表状态检查 + 回填任务触发。

GET  /api/sync/status  各表数据量/最新日期/是否需要更新
POST /api/sync/run     启动回填任务（全局同时只允许一个 running）
GET  /api/sync/jobs    任务列表（含日志尾部）

回填通过 subprocess 以 `sys.executable -m ...` 方式启动，
环境变量继承（TUSHARE_TOKEN、DATABASE_URL 等），
日志落到项目根 logs/sync_{job_id}.log。
"""
import logging
import os
import subprocess
import sys
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import _conn

log = logging.getLogger(__name__)
router = APIRouter()

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 表元数据：key / 中文名 / 分组 / 日期列(None=无) / 回填模块 / --only 参数
# module: fundamentals=基本面全量命令 / extra=增量 / full=全量接口 / None=无自动命令
TABLES = [
    {"key": "daily_bars", "name": "行情日线", "group": "行情",
     "date_col": "trade_date", "module": None, "only": None},
    # 基本面
    {"key": "company_info", "name": "公司基本信息", "group": "基本面",
     "date_col": None, "module": "fundamentals", "only": None},
    {"key": "fin_income", "name": "利润表", "group": "基本面",
     "date_col": "end_date", "module": "fundamentals", "only": None},
    {"key": "fin_balance", "name": "资产负债表", "group": "基本面",
     "date_col": "end_date", "module": "fundamentals", "only": None},
    {"key": "fin_cashflow", "name": "现金流量表", "group": "基本面",
     "date_col": "end_date", "module": "fundamentals", "only": None},
    {"key": "fin_indicator", "name": "财务指标", "group": "基本面",
     "date_col": "end_date", "module": "fundamentals", "only": None},
    {"key": "top_holders", "name": "十大股东", "group": "基本面",
     "date_col": "report_date", "module": "fundamentals", "only": None},
    {"key": "holder_number", "name": "股东人数", "group": "基本面",
     "date_col": "report_date", "module": "fundamentals", "only": None},
    {"key": "pledge_info", "name": "股权质押", "group": "基本面",
     "date_col": "stat_date", "module": "fundamentals", "only": None},
    # 增量
    {"key": "daily_basic", "name": "每日指标", "group": "增量",
     "date_col": "trade_date", "module": "extra", "only": "daily_basic"},
    {"key": "moneyflow", "name": "资金流向", "group": "增量",
     "date_col": "trade_date", "module": "extra", "only": "moneyflow"},
    {"key": "suspend", "name": "停复牌", "group": "增量",
     "date_col": "suspend_date", "module": "extra", "only": "moneyflow"},
    {"key": "dividend", "name": "分红送股", "group": "增量",
     "date_col": "ann_date", "module": "extra", "only": "dividend"},
    {"key": "forecast", "name": "业绩预告", "group": "增量",
     "date_col": "ann_date", "module": "extra", "only": "forecast"},
    {"key": "express", "name": "业绩快报", "group": "增量",
     "date_col": "ann_date", "module": "extra", "only": "forecast"},
    # 全量接口
    {"key": "fina_mainbz", "name": "主营构成", "group": "全量接口",
     "date_col": "end_date", "module": "full", "only": "mainbz"},
    {"key": "company_detail", "name": "公司详情", "group": "全量接口",
     "date_col": None, "module": "full", "only": "company_detail"},
    {"key": "namechange", "name": "曾用名", "group": "全量接口",
     "date_col": "start_date", "module": "full", "only": "namechange"},
    {"key": "top_list", "name": "龙虎榜", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "top_list"},
    {"key": "top_inst", "name": "机构明细", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "top_list"},
    {"key": "index_daily", "name": "指数日线", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "index"},
    {"key": "moneyflow_hsgt", "name": "北向资金", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "hsgt_flow"},
    {"key": "hsgt_top10", "name": "陆股通十大", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "hsgt_top10"},
    {"key": "disclosure_date", "name": "披露计划", "group": "全量接口",
     "date_col": "end_date", "module": "full", "only": "disclosure"},
    {"key": "margin", "name": "两融汇总", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "margin"},
    {"key": "margin_detail", "name": "两融明细", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "margin"},
    {"key": "stk_limit", "name": "涨跌停", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "stk_limit"},
    {"key": "fina_audit", "name": "审计意见", "group": "全量接口",
     "date_col": "end_date", "module": "full", "only": "fina_audit"},
    {"key": "new_share", "name": "IPO新股", "group": "全量接口",
     "date_col": "list_date", "module": "full", "only": "new_share"},
    {"key": "managers", "name": "管理层", "group": "全量接口",
     "date_col": None, "module": "full", "only": "managers"},
    {"key": "share_float", "name": "限售解禁", "group": "全量接口",
     "date_col": "float_date", "module": "full", "only": "share_float"},
    {"key": "block_trade", "name": "大宗交易", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "block_trade"},
    # 15000积分档补全
    {"key": "adj_factor", "name": "复权因子", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "adj_factor"},
    {"key": "holder_trade", "name": "股东增减持", "group": "全量接口",
     "date_col": "ann_date", "module": "full", "only": "holdertrade"},
    {"key": "daily_ts", "name": "A股日线(Tushare)", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "daily_ts"},
    {"key": "repurchase", "name": "股票回购", "group": "全量接口",
     "date_col": "ann_date", "module": "full", "only": "repurchase"},
    {"key": "pledge_detail", "name": "质押明细", "group": "全量接口",
     "date_col": "ann_date", "module": "full", "only": "pledge_detail"},
    {"key": "index_basic", "name": "指数基本信息", "group": "全量接口",
     "date_col": None, "module": "full", "only": "index_info"},
    {"key": "index_weight", "name": "指数权重", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "index_info"},
    {"key": "index_member", "name": "指数成分", "group": "全量接口",
     "date_col": None, "module": "full", "only": "index_info"},
    {"key": "cyq_perf", "name": "每日筹码分布", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "cyq_perf"},
    {"key": "hk_hold", "name": "沪深港股通持股", "group": "全量接口",
     "date_col": "trade_date", "module": "full", "only": "hk_hold"},
]

# 按日更新的日期列（最新 < 今天即需更新）；其余日期列按季度判定
DAILY_COLS = {"trade_date", "suspend_date", "ann_date", "float_date"}


def _needs_update(date_col: str, latest, rows: int) -> bool:
    today = date.today()
    if latest is None:
        return rows == 0
    if date_col in DAILY_COLS:
        return latest < today
    qm = ((today.month - 1) // 3) * 3 + 1
    quarter_start = date(today.year, qm, 1)
    return latest < quarter_start


@router.get("/api/sync/status")
def sync_status():
    """各表数据量 / 最新日期 / 是否需要更新。"""
    out = []
    with _conn() as conn:
        with conn.cursor() as cur:
            for t in TABLES:
                key, dc = t["key"], t["date_col"]
                try:
                    if dc:
                        cur.execute(
                            f'SELECT COUNT(*), MAX("{dc}") FROM "{key}"')
                    else:
                        cur.execute(f'SELECT COUNT(*) FROM "{key}"')
                    row = cur.fetchone()
                    rows = row[0]
                    latest = row[1] if dc else None
                    missing = False
                except Exception:  # noqa: BLE001 表不存在等
                    conn.rollback()
                    rows, latest, missing = 0, None, True
                if missing:
                    needs = True
                elif dc is None:
                    needs = rows == 0
                else:
                    needs = _needs_update(dc, latest, rows)
                out.append({
                    "key": key, "name": t["name"], "group": t["group"],
                    "rows": rows,
                    "latest_date": latest.isoformat() if latest else None,
                    "needs_update": needs, "missing": missing,
                    "has_command": t["module"] is not None,
                })
    return out


# ---------------------------------------------------------------- 任务管理

_jobs: dict = {}
_jobs_lock = threading.Lock()


class RunBody(BaseModel):
    table: str


def _build_cmd(t: dict):
    mod = t["module"]
    if mod == "fundamentals":
        return [sys.executable, "-m", "fetcher.jobs.backfill_fundamentals",
                "--source", "tushare"]
    if mod == "extra":
        return [sys.executable, "-m", "fetcher.jobs.backfill_tushare_extra",
                "--only", t["only"]]
    if mod == "full":
        return [sys.executable, "-m", "fetcher.jobs.backfill_tushare_full",
                "--only", t["only"]]
    return None


def _watch(job_id: str, proc: "subprocess.Popen", log_f) -> None:
    rc = proc.wait()
    log_f.close()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job["status"] = "done" if rc == 0 else "failed"
            job["finished_at"] = datetime.now().isoformat(timespec="seconds")
    log.info("同步任务 %s 结束，返回码 %s", job_id, rc)


@router.post("/api/sync/run")
def sync_run(body: RunBody):
    """启动回填任务。全局同时只允许一个 running 任务，否则 409。"""
    t = next((x for x in TABLES if x["key"] == body.table), None)
    if not t:
        raise HTTPException(status_code=404, detail=f"未知表：{body.table}")
    cmd = _build_cmd(t)
    if not cmd:
        raise HTTPException(status_code=400,
                            detail=f"表 {body.table} 无自动回填命令")
    with _jobs_lock:
        for j in _jobs.values():
            if j["status"] == "running":
                raise HTTPException(
                    status_code=409,
                    detail=f"已有任务运行中：{j['table_name']}（{j['job_id']}）")
        job_id = uuid.uuid4().hex[:8]
        log_path = LOG_DIR / f"sync_{job_id}.log"
        log_f = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT), stdout=log_f, stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        _jobs[job_id] = {
            "job_id": job_id, "table": t["key"], "table_name": t["name"],
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None, "log_file": str(log_path),
        }
    threading.Thread(target=_watch, args=(job_id, proc, log_f),
                     daemon=True).start()
    log.info("启动同步任务 %s：%s", job_id, " ".join(cmd))
    return {"job_id": job_id}


def _log_tail(path: str, n: int = 30) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


@router.get("/api/sync/jobs")
def sync_jobs():
    """任务列表：按开始时间倒序，最多 20 个，含日志尾部。"""
    out = []
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda j: j["started_at"],
                      reverse=True)[:20]
        for j in jobs:
            out.append({
                "job_id": j["job_id"], "table": j["table"],
                "table_name": j["table_name"], "status": j["status"],
                "started_at": j["started_at"], "finished_at": j["finished_at"],
                "log_tail": _log_tail(j["log_file"]),
            })
    return out
