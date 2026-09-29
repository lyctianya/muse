"""相册域：相册 / 照片。

挂载前缀：/api/gallery（由 api/main.py 统一加）。
权限：
    gallery:view    查看相册与照片
    gallery:upload  新建相册、上传照片
    gallery:manage  删除任意相册/照片（无此权限只能删自己的）

照片文件走平台存储（domain='gallery'），展示用 /api/files/{id}。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.platform import storage
from api.platform.auth import get_current_user, require_perm
from api.platform.deps import _conn

router = APIRouter()

SCHEMA_GALLERY = """
CREATE TABLE IF NOT EXISTS albums (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    cover_file_id TEXT,
    owner_id      TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS photos (
    id         TEXT PRIMARY KEY,
    album_id   TEXT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    file_id    TEXT NOT NULL,
    caption    TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_photos_album ON photos (album_id, sort_order);
"""


def ensure_schema() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_GALLERY)
        conn.commit()


class AlbumIn(BaseModel):
    title: str
    description: str = ""
    cover_file_id: str | None = None


class PhotoIn(BaseModel):
    file_id: str
    caption: str = ""


@router.get("/albums", dependencies=[Depends(require_perm("gallery:view"))])
def list_albums():
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.title, a.description, a.cover_file_id, a.owner_id, "
            "a.created_at, COUNT(p.id) FROM albums a "
            "LEFT JOIN photos p ON p.album_id = a.id "
            "GROUP BY a.id ORDER BY a.created_at DESC")
        items = []
        for r in cur.fetchall():
            items.append({
                "id": r[0], "title": r[1], "description": r[2],
                "cover_file_id": r[3], "owner_id": r[4],
                "created_at": r[5].isoformat() if r[5] else None,
                "photo_count": r[6],
            })
    return {"items": items}


@router.post("/albums", dependencies=[Depends(require_perm("gallery:upload"))])
def create_album(body: AlbumIn, user: dict = Depends(get_current_user)):
    ensure_schema()
    if not body.title.strip():
        raise HTTPException(400, "相册标题不能为空")
    aid = uuid.uuid4().hex
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO albums (id, title, description, cover_file_id, owner_id) "
            "VALUES (%s,%s,%s,%s,%s)",
            (aid, body.title.strip(), body.description, body.cover_file_id,
             str(user["id"])))
        conn.commit()
    return {"id": aid}


@router.get("/albums/{aid}", dependencies=[Depends(require_perm("gallery:view"))])
def get_album(aid: str):
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, description, cover_file_id, owner_id, created_at "
                    "FROM albums WHERE id = %s", (aid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "相册不存在")
        album = {"id": row[0], "title": row[1], "description": row[2],
                 "cover_file_id": row[3], "owner_id": row[4],
                 "created_at": row[5].isoformat() if row[5] else None}
        cur.execute("SELECT id, file_id, caption, sort_order, created_at FROM photos "
                    "WHERE album_id = %s ORDER BY sort_order, created_at", (aid,))
        album["photos"] = [
            {"id": r[0], "file_id": r[1], "caption": r[2], "sort_order": r[3],
             "created_at": r[4].isoformat() if r[4] else None,
             "url": f"/api/files/{r[1]}"}
            for r in cur.fetchall()
        ]
    return album


@router.delete("/albums/{aid}")
def delete_album(aid: str, user: dict = Depends(get_current_user)):
    ensure_schema()
    perms = user.get("permissions", [])
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT owner_id FROM albums WHERE id = %s", (aid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "相册不存在")
        if str(row[0]) != str(user["id"]) and "gallery:manage" not in perms:
            raise HTTPException(403, "只能删除自己的相册")
        # 级联删照片文件
        cur.execute("SELECT file_id FROM photos WHERE album_id = %s", (aid,))
        fids = [r[0] for r in cur.fetchall()]
        cur.execute("DELETE FROM albums WHERE id = %s", (aid,))
        conn.commit()
    for fid in fids:
        storage.delete_file(fid)
    return {"ok": True}


@router.post("/albums/{aid}/photos",
             dependencies=[Depends(require_perm("gallery:upload"))])
def add_photos(aid: str, body: list[PhotoIn]):
    """批量添加照片（前端先调 /api/files/upload 拿到 file_id）。"""
    ensure_schema()
    if not body:
        raise HTTPException(400, "照片列表为空")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM albums WHERE id = %s", (aid,))
        if not cur.fetchone():
            raise HTTPException(404, "相册不存在")
        cur.execute("SELECT COALESCE(MAX(sort_order), -1) FROM photos WHERE album_id = %s",
                    (aid,))
        order = cur.fetchone()[0] + 1
        ids = []
        for p in body:
            pid = uuid.uuid4().hex
            cur.execute(
                "INSERT INTO photos (id, album_id, file_id, caption, sort_order) "
                "VALUES (%s,%s,%s,%s,%s)",
                (pid, aid, p.file_id, p.caption, order))
            order += 1
            ids.append(pid)
        # 首张照片自动设为封面
        cur.execute("UPDATE albums SET cover_file_id = %s WHERE id = %s "
                    "AND cover_file_id IS NULL", (body[0].file_id, aid))
        conn.commit()
    return {"ids": ids}


@router.delete("/photos/{pid}")
def delete_photo(pid: str, user: dict = Depends(get_current_user)):
    ensure_schema()
    perms = user.get("permissions", [])
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT p.file_id, a.owner_id FROM photos p "
                    "JOIN albums a ON a.id = p.album_id WHERE p.id = %s", (pid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "照片不存在")
        if str(row[1]) != str(user["id"]) and "gallery:manage" not in perms:
            raise HTTPException(403, "只能删除自己相册的照片")
        cur.execute("DELETE FROM photos WHERE id = %s", (pid,))
        conn.commit()
        fid = row[0]
    storage.delete_file(fid)
    return {"ok": True}
