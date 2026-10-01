"""AI 对话域：模型配置 / 会话 / 消息 / SSE 流式对话。

挂载前缀：/api/ai（由 api/main.py 统一加）。
权限：
    ai:use     发起对话、管理自己的会话与个人模型
    ai:manage  管理全局共享模型

模型归属：owner_user_id 为 NULL = 全局共享（需 ai:manage），否则为个人模型。
会话按 user_id 隔离。
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.modules.ai import crypto
from api.modules.ai.provider import ProviderError, extract_delta_text, stream_chat
from api.platform.auth import get_current_user, require_perm
from api.platform.deps import _conn

router = APIRouter()

SCHEMA_AI = """
CREATE TABLE IF NOT EXISTS ai_models (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    provider      TEXT NOT NULL DEFAULT 'openai_compatible',
    model_id      TEXT NOT NULL,
    base_url      TEXT NOT NULL,
    api_key_enc   TEXT NOT NULL DEFAULT '',
    enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    owner_user_id TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_models_owner ON ai_models (owner_user_id, enabled, sort_order);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '新对话',
    model_id   TEXT,
    pinned     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_conv_user ON ai_conversations (user_id, pinned DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS ai_messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_msg_conv ON ai_messages (conversation_id, created_at);
"""


def ensure_schema() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_AI)
        conn.commit()


# ---------------- 模型 ----------------

class ModelIn(BaseModel):
    name: str
    provider: str = "openai_compatible"
    model_id: str
    base_url: str
    api_key: str = ""          # 明文传入，后端加密存储；为空表示不修改
    enabled: bool = True
    sort_order: int = 0
    shared: bool = False       # True=全局共享（需 ai:manage）


def _model_row(row, include_key_mask=True) -> dict:
    (mid, name, provider, model_id, base_url, api_key_enc, enabled,
     sort_order, owner, created_at, updated_at) = row
    d = {
        "id": mid, "name": name, "provider": provider, "model_id": model_id,
        "base_url": base_url, "enabled": enabled, "sort_order": sort_order,
        "shared": owner is None,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }
    if include_key_mask:
        d["api_key_masked"] = crypto.mask_key(api_key_enc or "")
        d["has_key"] = bool(api_key_enc)
    return d


def _get_model(cur, model_id: str, user_id: str) -> tuple | None:
    """取用户可用的模型：全局启用的 + 自己的。"""
    cur.execute(
        """SELECT id, name, provider, model_id, base_url, api_key_enc, enabled,
                  sort_order, owner_user_id, created_at, updated_at
           FROM ai_models WHERE id = %s AND enabled = TRUE
             AND (owner_user_id IS NULL OR owner_user_id = %s)""",
        (model_id, user_id),
    )
    return cur.fetchone()


@router.get("/models", dependencies=[Depends(require_perm("ai:use"))])
def list_models(user=Depends(get_current_user)):
    ensure_schema()
    uid = user["id"]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, name, provider, model_id, base_url, api_key_enc, enabled,
                      sort_order, owner_user_id, created_at, updated_at
               FROM ai_models
               WHERE enabled = TRUE AND (owner_user_id IS NULL OR owner_user_id = %s)
               ORDER BY sort_order, created_at""",
            (uid,),
        )
        return [_model_row(r) for r in cur.fetchall()]


@router.post("/models", dependencies=[Depends(require_perm("ai:use"))])
def create_model(body: ModelIn, user=Depends(get_current_user)):
    ensure_schema()
    uid = user["id"]
    if body.shared and not _has_perm(uid, "ai:manage"):
        raise HTTPException(403, "需要 ai:manage 权限才能创建共享模型")
    mid = uuid.uuid4().hex
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ai_models
               (id, name, provider, model_id, base_url, api_key_enc, enabled,
                sort_order, owner_user_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (mid, body.name.strip(), body.provider, body.model_id.strip(),
             body.base_url.strip().rstrip("/"), crypto.encrypt_key(body.api_key),
             body.enabled, body.sort_order,
             None if body.shared else uid),
        )
        conn.commit()
    return {"id": mid}


@router.put("/models/{mid}", dependencies=[Depends(require_perm("ai:use"))])
def update_model(mid: str, body: ModelIn, user=Depends(get_current_user)):
    ensure_schema()
    uid = user["id"]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT owner_user_id, api_key_enc FROM ai_models WHERE id = %s", (mid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "模型不存在")
        owner, old_enc = row
        if owner is None and not _has_perm(uid, "ai:manage"):
            raise HTTPException(403, "需要 ai:manage 权限")
        if owner is not None and owner != uid:
            raise HTTPException(403, "无权修改他人模型")
        new_enc = crypto.encrypt_key(body.api_key) if body.api_key else old_enc
        new_owner = owner
        if body.shared != (owner is None):
            if body.shared and not _has_perm(uid, "ai:manage"):
                raise HTTPException(403, "需要 ai:manage 权限")
            new_owner = None if body.shared else uid
        cur.execute(
            """UPDATE ai_models SET name=%s, provider=%s, model_id=%s, base_url=%s,
                  api_key_enc=%s, enabled=%s, sort_order=%s, owner_user_id=%s,
                  updated_at=now() WHERE id=%s""",
            (body.name.strip(), body.provider, body.model_id.strip(),
             body.base_url.strip().rstrip("/"), new_enc, body.enabled,
             body.sort_order, new_owner, mid),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/models/{mid}", dependencies=[Depends(require_perm("ai:use"))])
def delete_model(mid: str, user=Depends(get_current_user)):
    ensure_schema()
    uid = user["id"]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT owner_user_id FROM ai_models WHERE id = %s", (mid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "模型不存在")
        owner = row[0]
        if owner is None and not _has_perm(uid, "ai:manage"):
            raise HTTPException(403, "需要 ai:manage 权限")
        if owner is not None and owner != uid:
            raise HTTPException(403, "无权删除他人模型")
        cur.execute("DELETE FROM ai_models WHERE id = %s", (mid,))
        conn.commit()
    return {"ok": True}


def _has_perm(user_id: str, perm_key: str) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM role_permissions rp
               JOIN permissions p ON p.id = rp.permission_id
               JOIN user_roles ur ON ur.role_id = rp.role_id
               WHERE ur.user_id = %s AND p.key = %s LIMIT 1""",
            (user_id, perm_key),
        )
        return cur.fetchone() is not None


# ---------------- 会话 ----------------

class ConvIn(BaseModel):
    title: str = "新对话"
    model_id: str | None = None


@router.get("/conversations", dependencies=[Depends(require_perm("ai:use"))])
def list_conversations(user=Depends(get_current_user)):
    ensure_schema()
    uid = user["id"]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, title, model_id, pinned, created_at, updated_at
               FROM ai_conversations WHERE user_id = %s
               ORDER BY pinned DESC, updated_at DESC LIMIT 200""",
            (uid,),
        )
        out = []
        for r in cur.fetchall():
            cid, title, model_id, pinned, ca, ua = r
            out.append({
                "id": cid, "title": title, "model_id": model_id, "pinned": pinned,
                "created_at": ca.isoformat() if ca else None,
                "updated_at": ua.isoformat() if ua else None,
            })
        return out


@router.post("/conversations", dependencies=[Depends(require_perm("ai:use"))])
def create_conversation(body: ConvIn, user=Depends(get_current_user)):
    ensure_schema()
    cid = uuid.uuid4().hex
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ai_conversations (id, user_id, title, model_id) VALUES (%s,%s,%s,%s)",
            (cid, user["id"], body.title.strip() or "新对话", body.model_id),
        )
        conn.commit()
    return {"id": cid}


@router.put("/conversations/{cid}", dependencies=[Depends(require_perm("ai:use"))])
def update_conversation(cid: str, body: dict, user=Depends(get_current_user)):
    """改名 / 置顶：{title?, pinned?, model_id?}"""
    ensure_schema()
    uid = user["id"]
    sets, vals = [], []
    if "title" in body:
        sets.append("title = %s")
        vals.append(str(body["title"]).strip()[:100] or "新对话")
    if "pinned" in body:
        sets.append("pinned = %s")
        vals.append(bool(body["pinned"]))
    if "model_id" in body:
        sets.append("model_id = %s")
        vals.append(body["model_id"])
    if not sets:
        return {"ok": True}
    sets.append("updated_at = now()")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM ai_conversations WHERE id = %s AND user_id = %s", (cid, uid))
        if not cur.fetchone():
            raise HTTPException(404, "会话不存在")
        cur.execute(f"UPDATE ai_conversations SET {', '.join(sets)} WHERE id = %s",
                    (*vals, cid))
        conn.commit()
    return {"ok": True}


@router.delete("/conversations/{cid}", dependencies=[Depends(require_perm("ai:use"))])
def delete_conversation(cid: str, user=Depends(get_current_user)):
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM ai_conversations WHERE id = %s AND user_id = %s",
                    (cid, user["id"]))
        conn.commit()
    return {"ok": True}


@router.get("/conversations/{cid}/messages", dependencies=[Depends(require_perm("ai:use"))])
def list_messages(cid: str, user=Depends(get_current_user)):
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM ai_conversations WHERE id = %s AND user_id = %s",
                    (cid, user["id"]))
        if not cur.fetchone():
            raise HTTPException(404, "会话不存在")
        cur.execute(
            "SELECT id, role, content, created_at FROM ai_messages "
            "WHERE conversation_id = %s ORDER BY created_at LIMIT 500",
            (cid,),
        )
        return [
            {"id": r[0], "role": r[1], "content": r[2],
             "created_at": r[3].isoformat() if r[3] else None}
            for r in cur.fetchall()
        ]


# ---------------- SSE 对话 ----------------

class ChatIn(BaseModel):
    conversation_id: str | None = None
    model_id: str | None = None
    content: str
    context_len: int = 20  # 带最近 N 条历史


@router.post("/chat", dependencies=[Depends(require_perm("ai:use"))])
async def chat(body: ChatIn, user=Depends(get_current_user)):
    ensure_schema()
    uid = user["id"]
    text = (body.content or "").strip()
    if not text:
        raise HTTPException(400, "内容为空")
    if len(text) > 20000:
        raise HTTPException(400, "单条消息过长")

    with _conn() as conn, conn.cursor() as cur:
        # 会话：新建或校验归属
        cid = body.conversation_id
        if cid:
            cur.execute("SELECT id, model_id FROM ai_conversations WHERE id=%s AND user_id=%s",
                        (cid, uid))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "会话不存在")
            model_id = body.model_id or row[1]
        else:
            cid = uuid.uuid4().hex
            model_id = body.model_id
            title = text[:20]
            cur.execute(
                "INSERT INTO ai_conversations (id, user_id, title, model_id) VALUES (%s,%s,%s,%s)",
                (cid, uid, title, model_id),
            )
        if not model_id:
            raise HTTPException(400, "未选择模型")
        mrow = _get_model(cur, model_id, uid)
        if not mrow:
            raise HTTPException(400, "模型不可用")
        mid, name, provider, model_name, base_url, api_key_enc = mrow[:6]
        api_key = crypto.decrypt_key(api_key_enc or "")

        # 历史上下文
        n = max(1, min(body.context_len, 50))
        cur.execute(
            "SELECT role, content FROM ai_messages WHERE conversation_id=%s "
            "ORDER BY created_at DESC LIMIT %s",
            (cid, n),
        )
        hist = [{"role": r[0], "content": r[1]} for r in reversed(cur.fetchall())]
        messages = hist + [{"role": "user", "content": text}]

        # 先落库用户消息
        cur.execute(
            "INSERT INTO ai_messages (id, conversation_id, role, content) VALUES (%s,%s,'user',%s)",
            (uuid.uuid4().hex, cid, text),
        )
        cur.execute("UPDATE ai_conversations SET updated_at=now(), model_id=%s WHERE id=%s",
                    (mid, cid))
        conn.commit()

    async def gen():
        # 首包：会话 id（前端据此建会话）
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': cid})}\n\n"
        full = []
        try:
            async for chunk in stream_chat(base_url, api_key, model_name, messages):
                piece = extract_delta_text(chunk)
                if piece:
                    full.append(piece)
                    yield f"data: {json.dumps({'type': 'delta', 'text': piece})}\n\n"
        except ProviderError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
            return
        # 落库 assistant 回复
        reply = "".join(full)
        try:
            with _conn() as conn2, conn2.cursor() as cur2:
                cur2.execute(
                    "INSERT INTO ai_messages (id, conversation_id, role, content) "
                    "VALUES (%s,%s,'assistant',%s)",
                    (uuid.uuid4().hex, cid, reply),
                )
                cur2.execute("UPDATE ai_conversations SET updated_at=now() WHERE id=%s", (cid,))
                conn2.commit()
        except Exception:
            pass
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
