"""博客域：文章 / 标签。

挂载前缀：/api/blog（由 api/main.py 统一加）。
权限：
    blog:view    查看已发布文章
    blog:manage  新建/编辑/发布/删除（含看草稿）

封面图走文件域：cover_file_id 关联 files 表，展示时用 /api/files/{id}。
"""
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.platform.auth import get_current_user, require_perm
from api.platform.deps import _conn

router = APIRouter()

SCHEMA_BLOG = """
CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    content_html  TEXT NOT NULL DEFAULT '',
    excerpt       TEXT NOT NULL DEFAULT '',
    cover_file_id TEXT,
    category      TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'draft',
    author_id     TEXT NOT NULL,
    published_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts (status, published_at DESC);
CREATE TABLE IF NOT EXISTS tags (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS post_tags (
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);
"""


def ensure_schema() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_BLOG)
        # 2026-10-01：Markdown 编辑器 → Tiptap 富文本，content_md 改名 content_html
        cur.execute("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'posts' AND column_name = 'content_md')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'posts' AND column_name = 'content_html') THEN
                    ALTER TABLE posts RENAME COLUMN content_md TO content_html;
                END IF;
            END $$;
        """)
        conn.commit()


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or uuid.uuid4().hex[:8]


def _excerpt(body: "PostIn") -> str:
    if body.excerpt:
        return body.excerpt
    text = re.sub(r"<[^>]+>", "", body.content_html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


class PostIn(BaseModel):
    title: str
    content_html: str = ""
    excerpt: str = ""
    cover_file_id: str | None = None
    category: str = ""
    status: str = "draft"
    tags: list[str] = []


def _row_to_post(row) -> dict:
    keys = ("id", "slug", "title", "excerpt", "cover_file_id", "category",
            "status", "author_id", "published_at", "created_at", "updated_at")
    d = dict(zip(keys, row))
    for k in ("published_at", "created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


def _tags_of(cur, post_id: str) -> list[str]:
    cur.execute("SELECT t.name FROM tags t JOIN post_tags pt ON pt.tag_id = t.id "
                "WHERE pt.post_id = %s ORDER BY t.name", (post_id,))
    return [r[0] for r in cur.fetchall()]


def _set_tags(cur, post_id: str, names: list[str]) -> None:
    cur.execute("DELETE FROM post_tags WHERE post_id = %s", (post_id,))
    for name in dict.fromkeys(n.strip() for n in names if n.strip()):
        tid = uuid.uuid4().hex
        cur.execute("INSERT INTO tags (id, name) VALUES (%s, %s) "
                    "ON CONFLICT (name) DO NOTHING RETURNING id", (tid, name))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM tags WHERE name = %s", (name,))
            row = cur.fetchone()
        cur.execute("INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) "
                    "ON CONFLICT DO NOTHING", (post_id, row[0]))


@router.get("/posts")
def list_posts(status: str = "", category: str = "", tag: str = "",
               limit: int = 50, offset: int = 0,
               user: dict = Depends(get_current_user)):
    """已发布列表；有 blog:manage 可加 status=draft 看草稿。"""
    ensure_schema()
    perms = user.get("permissions", [])
    can_manage = "blog:manage" in perms
    if "blog:view" not in perms and not can_manage:
        raise HTTPException(403, "无博客查看权限")
    where, params = [], []
    if status == "draft":
        if not can_manage:
            raise HTTPException(403, "无权查看草稿")
        where.append("p.status = 'draft'")
    else:
        where.append("p.status = 'published'")
    if category:
        where.append("p.category = %s")
        params.append(category)
    if tag:
        where.append("EXISTS (SELECT 1 FROM post_tags pt JOIN tags t ON t.id = pt.tag_id "
                     "WHERE pt.post_id = p.id AND t.name = %s)")
        params.append(tag)
    sql = ("SELECT p.id, p.slug, p.title, p.excerpt, p.cover_file_id, p.category, "
           "p.status, p.author_id, p.published_at, p.created_at, p.updated_at "
           "FROM posts p")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(p.published_at, p.created_at) DESC LIMIT %s OFFSET %s"
    params += [min(limit, 200), offset]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        items = [_row_to_post(r) for r in rows]
        for it in items:
            it["tags"] = _tags_of(cur, it["id"])
    return {"items": items}


@router.get("/posts/{slug}")
def get_post(slug: str, user: dict = Depends(get_current_user)):
    ensure_schema()
    perms = user.get("permissions", [])
    can_manage = "blog:manage" in perms
    if "blog:view" not in perms and not can_manage:
        raise HTTPException(403, "无博客查看权限")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT p.id, p.slug, p.title, p.excerpt, p.cover_file_id, p.category, "
            "p.status, p.author_id, p.published_at, p.created_at, p.updated_at, "
            "p.content_html FROM posts p WHERE p.slug = %s", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "文章不存在")
        keys = ("id", "slug", "title", "excerpt", "cover_file_id", "category",
                "status", "author_id", "published_at", "created_at", "updated_at",
                "content_html")
        d = dict(zip(keys, row))
        if d["status"] != "published" and not can_manage:
            raise HTTPException(403, "无权查看草稿")
        for k in ("published_at", "created_at", "updated_at"):
            if d.get(k):
                d[k] = d[k].isoformat()
        d["tags"] = _tags_of(cur, d["id"])
    return d


@router.post("/posts", dependencies=[Depends(require_perm("blog:manage"))])
def create_post(body: PostIn, user: dict = Depends(get_current_user)):
    ensure_schema()
    if body.status not in ("draft", "published"):
        raise HTTPException(400, "status 只能是 draft/published")
    pid, slug = uuid.uuid4().hex, _slugify(body.title)
    now = datetime.now(timezone.utc)
    with _conn() as conn, conn.cursor() as cur:
        # slug 冲突时加后缀
        cur.execute("SELECT 1 FROM posts WHERE slug = %s", (slug,))
        if cur.fetchone():
            slug = f"{slug}-{pid[:6]}"
        cur.execute(
            """INSERT INTO posts (id, slug, title, content_html, excerpt, cover_file_id,
                                  category, status, author_id, published_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (pid, slug, body.title, body.content_html,
             _excerpt(body), body.cover_file_id,
             body.category, body.status, str(user["id"]),
             now if body.status == "published" else None))
        _set_tags(cur, pid, body.tags)
        conn.commit()
    return {"id": pid, "slug": slug}


@router.put("/posts/{pid}", dependencies=[Depends(require_perm("blog:manage"))])
def update_post(pid: str, body: PostIn):
    ensure_schema()
    if body.status not in ("draft", "published"):
        raise HTTPException(400, "status 只能是 draft/published")
    now = datetime.now(timezone.utc)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM posts WHERE id = %s", (pid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "文章不存在")
        pub_at = now if (body.status == "published" and row[0] != "published") else None
        if pub_at:
            cur.execute(
                """UPDATE posts SET title=%s, content_html=%s, excerpt=%s, cover_file_id=%s,
                   category=%s, status=%s, published_at=%s, updated_at=now() WHERE id=%s""",
                (body.title, body.content_html, _excerpt(body),
                 body.cover_file_id, body.category, body.status, pub_at, pid))
        else:
            cur.execute(
                """UPDATE posts SET title=%s, content_html=%s, excerpt=%s, cover_file_id=%s,
                   category=%s, status=%s, updated_at=now() WHERE id=%s""",
                (body.title, body.content_html, _excerpt(body),
                 body.cover_file_id, body.category, body.status, pid))
        _set_tags(cur, pid, body.tags)
        conn.commit()
    return {"ok": True}


@router.delete("/posts/{pid}", dependencies=[Depends(require_perm("blog:manage"))])
def delete_post(pid: str):
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM posts WHERE id = %s", (pid,))
        conn.commit()
    return {"ok": True}


@router.get("/tags", dependencies=[Depends(require_perm("blog:view"))])
def list_tags():
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT t.name, COUNT(pt.post_id) FROM tags t "
                    "LEFT JOIN post_tags pt ON pt.tag_id = t.id "
                    "GROUP BY t.name ORDER BY 2 DESC, 1")
        return {"items": [{"name": r[0], "count": r[1]} for r in cur.fetchall()]}
