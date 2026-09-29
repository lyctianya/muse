"""同步水位表 sync_status 读写。

增量回填起点、前端「数据更新」页优先读此表，避免反复对业务表做 COUNT/MAX。
首次部署或怀疑水位不准时，调用 refresh_all() / refresh_tables() 从业务表扫一次。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable, Optional

from fetcher import db
from fetcher.sync_registry import TABLE_BY_KEY, TABLES

log = logging.getLogger(__name__)

_UPSERT = """
INSERT INTO sync_status (table_name, latest_date, row_count, last_synced_at, updated_at)
VALUES (%(table_name)s, %(latest_date)s, %(row_count)s, %(last_synced_at)s, now())
ON CONFLICT (table_name) DO UPDATE SET
    latest_date = EXCLUDED.latest_date,
    row_count = EXCLUDED.row_count,
    last_synced_at = EXCLUDED.last_synced_at,
    updated_at = now()
"""


def _safe_ident(name: str) -> bool:
    return bool(name) and name.replace("_", "").isalnum()


def get_latest(table: str) -> Optional[date]:
    """读 sync_status.latest_date；无记录返回 None。"""
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT latest_date FROM sync_status WHERE table_name = %s",
                (table,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as exc:  # noqa: BLE001
        log.warning("读 sync_status[%s] 失败：%s", table, exc)
        return None


def get_all() -> dict:
    """返回 {table_name: {latest_date, row_count, last_synced_at, updated_at}}。"""
    out = {}
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, latest_date, row_count, last_synced_at, updated_at "
                "FROM sync_status"
            )
            for r in cur.fetchall():
                out[r[0]] = {
                    "latest_date": r[1],
                    "row_count": r[2] or 0,
                    "last_synced_at": r[3],
                    "updated_at": r[4],
                }
    except Exception as exc:  # noqa: BLE001
        log.warning("读 sync_status 全表失败：%s", exc)
    return out


def upsert(
    table: str,
    *,
    latest_date: Optional[date] = None,
    row_count: int = 0,
    last_synced_at: Optional[datetime] = None,
) -> None:
    """写入/更新一条水位。"""
    with db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            _UPSERT,
            {
                "table_name": table,
                "latest_date": latest_date,
                "row_count": int(row_count or 0),
                "last_synced_at": last_synced_at or datetime.now(),
            },
        )


def refresh_one(table: str, date_col: Optional[str] = None) -> dict:
    """从业务表扫 COUNT / MAX，写回 sync_status。返回写入结果。"""
    meta = TABLE_BY_KEY.get(table, {})
    dc = date_col if date_col is not None else meta.get("date_col")
    if not _safe_ident(table) or (dc and not _safe_ident(dc)):
        return {"table": table, "ok": False, "error": "invalid ident"}
    missing = False
    rows, latest = 0, None
    try:
        with db.get_pool().connection() as conn, conn.cursor() as cur:
            if dc:
                cur.execute(f'SELECT COUNT(*), MAX("{dc}") FROM "{table}"')  # noqa: S608
                rows, latest = cur.fetchone()
            else:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
                rows = cur.fetchone()[0]
                latest = None
    except Exception as exc:  # noqa: BLE001
        log.warning("扫描业务表 %s 失败：%s", table, exc)
        missing = True
        rows, latest = 0, None
    try:
        upsert(table, latest_date=latest, row_count=rows)
    except Exception as exc:  # noqa: BLE001
        log.warning("写 sync_status[%s] 失败：%s", table, exc)
        return {"table": table, "ok": False, "error": str(exc), "missing": missing}
    return {
        "table": table, "ok": True, "missing": missing,
        "rows": rows,
        "latest_date": latest.isoformat() if latest else None,
    }


def refresh_tables(tables: Iterable[str]) -> list:
    """批量从业务表刷新水位。"""
    results = []
    for t in tables:
        results.append(refresh_one(t))
    return results


def refresh_all() -> list:
    """按注册表刷新全部水位（首次部署 / 怀疑不准时用）。"""
    return refresh_tables(t["key"] for t in TABLES)


def mark_synced_from_job(job_only: str) -> list:
    """按 JOB_TABLES 映射，刷新某回填任务影响到的表。"""
    from fetcher.sync_registry import JOB_TABLES
    tables = JOB_TABLES.get(job_only) or []
    if not tables:
        log.warning("JOB_TABLES 无映射：%s", job_only)
        return []
    log.info("刷新 sync_status：job=%s tables=%s", job_only, tables)
    return refresh_tables(tables)
