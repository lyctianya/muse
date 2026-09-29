"""游戏域：排行榜。

挂载前缀：/api/game（由 api/main.py 统一加）。
权限：
    game:view    进入游戏页、查看排行榜、提交成绩（需登录）

游戏本体是纯前端（three.js），后端只存成绩。
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.platform.auth import get_current_user, require_perm
from api.platform.deps import _conn

router = APIRouter()

SCHEMA_GAME = """
CREATE TABLE IF NOT EXISTS game_scores (
    id         TEXT PRIMARY KEY,
    game_id    TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    username   TEXT NOT NULL DEFAULT '',
    score      INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_game_scores ON game_scores (game_id, score DESC);
"""


def ensure_schema() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_GAME)
        conn.commit()


class ScoreIn(BaseModel):
    game_id: str
    score: int


@router.get("/scores", dependencies=[Depends(require_perm("game:view"))])
def leaderboard(game_id: str, limit: int = 20):
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT username, score, created_at FROM game_scores "
            "WHERE game_id = %s ORDER BY score DESC, created_at LIMIT %s",
            (game_id, min(limit, 100)))
        return {"items": [
            {"username": r[0], "score": r[1],
             "created_at": r[2].isoformat() if r[2] else None}
            for r in cur.fetchall()
        ]}


@router.post("/scores", dependencies=[Depends(require_perm("game:view"))])
def submit_score(body: ScoreIn, user: dict = Depends(get_current_user)):
    ensure_schema()
    if not body.game_id or body.score < 0 or body.score > 10_000_000:
        raise HTTPException(400, "成绩不合法")
    sid = uuid.uuid4().hex
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO game_scores (id, game_id, user_id, username, score) "
            "VALUES (%s,%s,%s,%s,%s)",
            (sid, body.game_id[:64], str(user["id"]),
             (user.get("display_name") or user.get("username") or "")[:64],
             body.score))
        conn.commit()
    return {"id": sid}


@router.get("/my-best", dependencies=[Depends(require_perm("game:view"))])
def my_best(game_id: str, user: dict = Depends(get_current_user)):
    ensure_schema()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(score), 0) FROM game_scores "
                    "WHERE game_id = %s AND user_id = %s",
                    (game_id, str(user["id"])))
        return {"best": cur.fetchone()[0]}
