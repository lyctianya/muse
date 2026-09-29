"""数据同步管理：表状态检查 + 回填任务触发。

GET  /api/sync/status          读 sync_status 水位（不扫业务表）
POST /api/sync/refresh-status  从业务表重扫写入 sync_status
POST /api/sync/run             启动回填任务（全局同时只允许一个 running）
GET  /api/sync/jobs            任务列表（含日志尾部）

回填通过 subprocess 以 `sys.executable -m ...` 方式启动，
环境变量继承（TUSHARE_TOKEN、DATABASE_URL 等），
日志落到项目根 logs/sync_{job_id}.log。
任务成功结束后会刷新对应表的 sync_status。
"""
import logging
import os
import subprocess
import sys
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.platform.auth import require_perm

from fetcher.sync_freshness import needs_update
from fetcher.sync_registry import DAILY_COLS, TABLES
from fetcher import sync_status as ss

log = logging.getLogger(__name__)
router = APIRouter()

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _merge_dotenv(env: dict) -> dict:
    """把项目根 .env 合并进 env（已有键不覆盖）。"""
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return env
    try:
        for raw in dotenv.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            env.setdefault(k, v)
    except OSError as exc:
        log.warning("读取 .env 失败：%s", exc)
    return env


def _subprocess_env() -> dict:
    """回填子进程环境：继承当前进程 + 补齐 .env，并强制 UTF-8 日志。"""
    env = _merge_dotenv(os.environ.copy())
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PGCLIENTENCODING", "UTF8")
    return env


def _status_rows_from_watermark(watermarks: dict) -> list:
    """用 sync_status 水位 + TABLES 元数据拼前端行。"""
    out = []
    for t in TABLES:
        key, dc = t["key"], t["date_col"]
        wm = watermarks.get(key)
        if wm is None:
            rows, latest, missing = 0, None, False
            # 水位缺失 ≠ 业务表缺失；标记为需更新，提示用户点「重新扫描」
            needs = True
            watermark_missing = True
        else:
            rows = int(wm.get("row_count") or 0)
            latest = wm.get("latest_date")
            missing = False
            watermark_missing = False
            if dc is None:
                needs = rows == 0
            else:
                needs = needs_update(dc, latest, rows)
            # 行数为 0 一律视为需要更新（即使日期判定过不去）
            if rows == 0:
                needs = True
                missing = True
        last_synced = wm.get("last_synced_at") if wm else None
        out.append({
            "key": key, "name": t["name"], "group": t["group"],
            "rows": rows,
            "latest_date": latest.isoformat() if latest else None,
            "last_synced_at": (
                last_synced.isoformat(timespec="seconds")
                if last_synced else None
            ),
            "needs_update": needs, "missing": missing,
            "watermark_missing": watermark_missing,
            "has_command": t["module"] is not None,
        })
    return out


@router.get("/sync/status")
def sync_status():
    """各表数据量 / 最新日期 / 是否需要更新（读 sync_status，不扫业务表）。"""
    watermarks = ss.get_all()
    return _status_rows_from_watermark(watermarks)


class RefreshBody(BaseModel):
    tables: list[str] | None = None  # None / [] = 全部


@router.post("/sync/refresh-status")
def sync_refresh_status(body: RefreshBody | None = None):
    """从业务表扫 COUNT/MAX，写回 sync_status。首次部署或水位不准时用。"""
    tables = (body.tables if body and body.tables else None)
    if tables:
        results = ss.refresh_tables(tables)
    else:
        results = ss.refresh_all()
    watermarks = ss.get_all()
    return {
        "refreshed": results,
        "status": _status_rows_from_watermark(watermarks),
    }


# ---------------------------------------------------------------- 任务管理

_jobs: dict = {}
_jobs_lock = threading.Lock()


class RunBody(BaseModel):
    table: str


def _build_cmd(t: dict):
    mod = t["module"]
    if mod == "fundamentals":
        return [sys.executable, "-m", "fetcher.jobs.backfill_fundamentals",
                "--source", "tushare"], "fundamentals"
    if mod == "extra":
        return ([sys.executable, "-m", "fetcher.jobs.backfill_tushare_extra",
                 "--only", t["only"]], t["only"])
    if mod == "full":
        return ([sys.executable, "-m", "fetcher.jobs.backfill_tushare_full",
                 "--only", t["only"]], t["only"])
    return None, None


def _watch(job_id: str, proc: "subprocess.Popen", log_f, job_only: str) -> None:
    rc = proc.wait()
    log_f.close()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job["status"] = "done" if rc == 0 else "failed"
            job["finished_at"] = datetime.now().isoformat(timespec="seconds")
    # 成功时再扫一次水位（进程内 mark_synced 已写；此处兜底）
    if rc == 0 and job_only:
        try:
            ss.mark_synced_from_job(job_only)
        except Exception as exc:  # noqa: BLE001
            log.warning("任务结束后刷新 sync_status 失败：%s", exc)
    log.info("同步任务 %s 结束，返回码 %s", job_id, rc)


@router.post("/sync/run")
def sync_run(body: RunBody, _: dict = Depends(require_perm("sync:run"))):
    """启动回填任务。全局同时只允许一个 running 任务，否则 409。"""
    t = next((x for x in TABLES if x["key"] == body.table), None)
    if not t:
        raise HTTPException(status_code=404, detail=f"未知表：{body.table}")
    cmd, job_only = _build_cmd(t)
    if not cmd:
        raise HTTPException(status_code=400,
                            detail=f"表 {body.table} 无自动回填命令")

    env = _subprocess_env()
    # Tushare 回填任务必须有 token；缺了会秒退且日志难读，启动前直接拦下
    if t["module"] in ("fundamentals", "extra", "full"):
        if not (env.get("TUSHARE_TOKEN") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="未配置 TUSHARE_TOKEN：请写入项目根目录 .env 后重启 API",
            )

    with _jobs_lock:
        for j in _jobs.values():
            if j["status"] == "running":
                raise HTTPException(
                    status_code=409,
                    detail=f"已有任务运行中：{j['table_name']}（{j['job_id']}）")
        job_id = uuid.uuid4().hex[:8]
        log_path = LOG_DIR / f"sync_{job_id}.log"
        log_f = open(log_path, "w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd, cwd=str(ROOT), stdout=log_f, stderr=subprocess.STDOUT,
                env=env,
            )
        except Exception:
            log_f.close()
            raise
        _jobs[job_id] = {
            "job_id": job_id, "table": t["key"], "table_name": t["name"],
            "job_only": job_only,
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None, "log_file": str(log_path),
        }
    threading.Thread(target=_watch, args=(job_id, proc, log_f, job_only),
                     daemon=True).start()
    log.info("启动同步任务 %s：%s", job_id, " ".join(cmd))
    return {"job_id": job_id}


def _log_tail(path: str, n: int = 30) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


@router.get("/sync/jobs")
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
