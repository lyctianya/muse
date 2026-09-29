"""平台文件存储：本地磁盘后端 + 数据库元数据。

存储布局：{STORAGE_ROOT}/{domain}/{yyyyMM}/{uuid}{ext}
元数据表：public.files（id, domain, owner_id, filename, stored_path,
           mime, size_bytes, created_at）

以后要换 S3/OSS：实现同名函数 save_file/get_file/delete_file 即可，
router 层不用改。
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .deps import ROOT, _conn, log

STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", str(ROOT / "data" / "files")))

SCHEMA_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id          TEXT PRIMARY KEY,
    domain      TEXT NOT NULL DEFAULT 'files',
    owner_id    TEXT NOT NULL,
    filename    TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    mime        TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes  BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_files_owner ON files (owner_id);
CREATE INDEX IF NOT EXISTS idx_files_domain ON files (domain);
"""


def ensure_schema() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_FILES)
        conn.commit()


def save_file(content: bytes, filename: str, mime: str, owner_id: str,
              domain: str = "files") -> dict:
    """保存文件，返回元数据。"""
    ensure_schema()
    fid = uuid.uuid4().hex
    ext = Path(filename).suffix[:16]
    subdir = datetime.now(timezone.utc).strftime("%Y%m")
    rel = Path(domain) / subdir / f"{fid}{ext}"
    dest = STORAGE_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    meta = {
        "id": fid,
        "domain": domain,
        "owner_id": owner_id,
        "filename": filename,
        "stored_path": str(rel).replace("\\", "/"),
        "mime": mime or "application/octet-stream",
        "size_bytes": len(content),
    }
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO files (id, domain, owner_id, filename, stored_path,
                                  mime, size_bytes)
               VALUES (%(id)s, %(domain)s, %(owner_id)s, %(filename)s,
                       %(stored_path)s, %(mime)s, %(size_bytes)s)
               ON CONFLICT (id) DO NOTHING""",
            meta,
        )
        conn.commit()
    log.info("文件已保存：%s (%d bytes)", rel, len(content))
    return meta


def get_file(fid: str) -> dict | None:
    """取元数据；不存在返回 None。"""
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, domain, owner_id, filename, stored_path, mime, "
            "size_bytes, created_at FROM files WHERE id = %s",
            (fid,),
        )
        row = cur.fetchone()
    if not row:
        return None
    keys = ("id", "domain", "owner_id", "filename", "stored_path",
            "mime", "size_bytes", "created_at")
    return dict(zip(keys, row))


def file_path(meta: dict) -> Path:
    return STORAGE_ROOT / meta["stored_path"]


def list_files(owner_id: str | None = None, domain: str | None = None,
               limit: int = 100, offset: int = 0) -> list[dict]:
    ensure_schema()
    where, params = [], []
    if owner_id:
        where.append("owner_id = %s")
        params.append(owner_id)
    if domain:
        where.append("domain = %s")
        params.append(domain)
    sql = ("SELECT id, domain, owner_id, filename, mime, size_bytes, created_at "
           "FROM files")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params += [limit, offset]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    keys = ("id", "domain", "owner_id", "filename", "mime",
            "size_bytes", "created_at")
    return [dict(zip(keys, r)) for r in rows]


def delete_file(fid: str) -> bool:
    """删磁盘文件 + 元数据；不存在返回 False。"""
    meta = get_file(fid)
    if not meta:
        return False
    p = file_path(meta)
    if p.exists():
        p.unlink()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM files WHERE id = %s", (fid,))
        conn.commit()
    log.info("文件已删除：%s", fid)
    return True
