"""新闻60秒：每日要闻缓存与查询。

挂载前缀：/api/news60s（由 api/main.py 统一加）。
权限：
    news60s:view  查看新闻
    news60s:sync  手动同步 / 统计 / 连通性测试

数据源：https://60s.viki.moe/v2/60s（可用 NEWS60S_API_URL 覆盖）。
API 进程内每 30 分钟后台同步一次。
"""
from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query

from api.platform.auth import require_perm
from api.platform.deps import _conn, log

router = APIRouter()

DEFAULT_API_URL = "https://60s.viki.moe/v2/60s"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SCHEMA_NEWS60S = """
CREATE TABLE IF NOT EXISTS sixty_seconds_news (
    id           BIGSERIAL PRIMARY KEY,
    date         TEXT NOT NULL UNIQUE,
    news         JSONB NOT NULL DEFAULT '[]'::jsonb,
    image        TEXT,
    tip          TEXT,
    cover        TEXT,
    audio_music  TEXT,
    audio_news   TEXT,
    link         TEXT,
    day_of_week  TEXT,
    lunar_date   TEXT,
    sync_status  INT NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sixty_seconds_news_sync_status
    ON sixty_seconds_news (sync_status);
CREATE INDEX IF NOT EXISTS idx_sixty_seconds_news_created_at
    ON sixty_seconds_news (created_at DESC);
"""

_stop_event = threading.Event()
_sync_thread: threading.Thread | None = None
_sync_lock = threading.Lock()


def ensure_schema() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_NEWS60S)
        conn.commit()


def _api_url() -> str:
    return os.environ.get("NEWS60S_API_URL", DEFAULT_API_URL).strip() or DEFAULT_API_URL


def _row_to_dict(row) -> dict:
    keys = (
        "id", "date", "news", "image", "tip", "cover",
        "audio_music", "audio_news", "link", "day_of_week", "lunar_date",
        "sync_status", "created_at", "updated_at",
    )
    d = dict(zip(keys, row))
    if isinstance(d.get("news"), str):
        try:
            d["news"] = json.loads(d["news"])
        except json.JSONDecodeError:
            d["news"] = []
    elif d.get("news") is None:
        d["news"] = []
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


def fetch_news_data() -> dict | None:
    """拉取上游 60s API，成功返回完整 JSON（含 code/data）。"""
    url = _api_url()
    log.info("[news60s] 开始获取：%s", url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.error("[news60s] 获取失败：%s", exc)
        return None

    if payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
        log.error("[news60s] API 返回异常：%s", payload)
        return None

    log.info("[news60s] 获取成功，日期：%s", payload["data"].get("date"))
    return payload


def save_news_data(api_payload: dict) -> bool:
    data = api_payload.get("data") or {}
    date = data.get("date")
    if not date or not DATE_RE.match(str(date)):
        log.error("[news60s] 无效日期：%s", date)
        return False

    audio = data.get("audio") or {}
    news = data.get("news") if isinstance(data.get("news"), list) else []
    now = datetime.now(timezone.utc)

    ensure_schema()
    try:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sixty_seconds_news (
                    date, news, image, tip, cover, audio_music, audio_news,
                    link, day_of_week, lunar_date, sync_status, created_at, updated_at
                ) VALUES (
                    %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s
                )
                ON CONFLICT (date) DO UPDATE SET
                    news = EXCLUDED.news,
                    image = EXCLUDED.image,
                    tip = EXCLUDED.tip,
                    cover = EXCLUDED.cover,
                    audio_music = EXCLUDED.audio_music,
                    audio_news = EXCLUDED.audio_news,
                    link = EXCLUDED.link,
                    day_of_week = EXCLUDED.day_of_week,
                    lunar_date = EXCLUDED.lunar_date,
                    sync_status = 1,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    date,
                    json.dumps(news, ensure_ascii=False),
                    data.get("image") or None,
                    data.get("tip") or None,
                    data.get("cover") or None,
                    audio.get("music") or None,
                    audio.get("news") or None,
                    data.get("link") or None,
                    data.get("day_of_week") or None,
                    data.get("lunar_date") or None,
                    now,
                    now,
                ),
            )
            conn.commit()
        log.info("[news60s] 保存成功：%s", date)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("[news60s] 保存失败：%s", exc)
        try:
            with _conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sixty_seconds_news (date, news, sync_status, updated_at)
                    VALUES (%s, '[]'::jsonb, 0, %s)
                    ON CONFLICT (date) DO UPDATE SET
                        sync_status = 0,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (date, now),
                )
                conn.commit()
        except Exception as upsert_exc:  # noqa: BLE001
            log.error("[news60s] 记录失败状态失败：%s", upsert_exc)
        return False


def sync_news_data() -> bool:
    with _sync_lock:
        payload = fetch_news_data()
        if not payload:
            return False
        return save_news_data(payload)


def start_sync_loop() -> None:
    """API 启动后：立即同步一次，之后每 30 分钟同步。"""
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return
    _stop_event.clear()

    def _loop() -> None:
        try:
            ensure_schema()
            sync_news_data()
        except Exception as exc:  # noqa: BLE001
            log.warning("[news60s] 启动同步失败：%s", exc)
        while not _stop_event.wait(30 * 60):
            try:
                sync_news_data()
            except Exception as exc:  # noqa: BLE001
                log.warning("[news60s] 定时同步失败：%s", exc)

    _sync_thread = threading.Thread(target=_loop, name="news60s-sync", daemon=True)
    _sync_thread.start()
    log.info("[news60s] 后台同步线程已启动（每 30 分钟）")


def stop_sync_loop() -> None:
    _stop_event.set()


@router.get("/news/latest", dependencies=[Depends(require_perm("news60s:view"))])
def latest_news():
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, date, news, image, tip, cover, audio_music, audio_news,
                   link, day_of_week, lunar_date, sync_status, created_at, updated_at
            FROM sixty_seconds_news
            WHERE sync_status = 1
            ORDER BY date DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()

    if not row:
        # 库空时尝试即时同步一次，避免首次打开无数据
        if sync_news_data():
            with _conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, date, news, image, tip, cover, audio_music, audio_news,
                           link, day_of_week, lunar_date, sync_status, created_at, updated_at
                    FROM sixty_seconds_news
                    WHERE sync_status = 1
                    ORDER BY date DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()

    if not row:
        raise HTTPException(404, "暂无新闻数据")
    return _row_to_dict(row)


@router.get("/news", dependencies=[Depends(require_perm("news60s:view"))])
def list_news(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    ensure_schema()
    offset = (page - 1) * page_size
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sixty_seconds_news")
        total = cur.fetchone()[0]
        cur.execute(
            """
            SELECT id, date, news, image, tip, cover, audio_music, audio_news,
                   link, day_of_week, lunar_date, sync_status, created_at, updated_at
            FROM sixty_seconds_news
            ORDER BY date DESC
            LIMIT %s OFFSET %s
            """,
            (page_size, offset),
        )
        rows = cur.fetchall()
    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
        "data": [_row_to_dict(r) for r in rows],
    }


@router.get("/news/{date}", dependencies=[Depends(require_perm("news60s:view"))])
def news_by_date(date: str):
    if not DATE_RE.match(date):
        raise HTTPException(400, "日期格式错误，应为 YYYY-MM-DD")
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, date, news, image, tip, cover, audio_music, audio_news,
                   link, day_of_week, lunar_date, sync_status, created_at, updated_at
            FROM sixty_seconds_news
            WHERE date = %s
            """,
            (date,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, f"未找到日期为 {date} 的新闻数据")
    return _row_to_dict(row)


@router.post("/sync", dependencies=[Depends(require_perm("news60s:sync"))])
def sync_now():
    ok = sync_news_data()
    if not ok:
        raise HTTPException(500, "60s 新闻数据同步失败，请查看日志")
    return {"ok": True, "message": "60s 新闻数据同步成功"}


@router.get("/stats", dependencies=[Depends(require_perm("news60s:sync"))])
def sync_stats():
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sixty_seconds_news")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sixty_seconds_news WHERE sync_status = 1")
        success = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sixty_seconds_news WHERE sync_status = 0")
        failed = cur.fetchone()[0]
        cur.execute(
            """
            SELECT date, sync_status, created_at
            FROM sixty_seconds_news
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        latest = cur.fetchone()
    latest_info = None
    if latest:
        latest_info = {
            "date": latest[0],
            "sync_status": latest[1],
            "created_at": latest[2].isoformat() if latest[2] else None,
        }
    rate = f"{(success / total * 100):.2f}%" if total else "0%"
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "successRate": rate,
        "latest": latest_info,
    }


@router.get("/test", dependencies=[Depends(require_perm("news60s:sync"))])
def test_connection():
    payload = fetch_news_data()
    if not payload:
        raise HTTPException(500, "API 连接失败或返回数据异常")
    data = payload["data"]
    news = data.get("news") if isinstance(data.get("news"), list) else []
    return {
        "status": "success",
        "date": data.get("date"),
        "newsCount": len(news),
        "message": "API 连接正常",
    }
