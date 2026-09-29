"""认证：密码注册/登录、JWT Cookie、Google OAuth、当前用户。"""
import logging
import os
import re
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.platform.deps import _conn

log = logging.getLogger(__name__)
router = APIRouter()

# ---------------- 配置 ----------------
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(32)
    log.warning("未配置 JWT_SECRET，已随机生成（重启后登录态失效）；请在 .env 中固定")

ACCESS_TTL = 2 * 3600      # access token 2 小时
REFRESH_TTL = 7 * 86400    # refresh token 7 天

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

COOKIE_KW = dict(httponly=True, samesite="lax", path="/")


# ---------------- 密码 ----------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def validate_password(pw: str) -> None:
    """8 位以上，含字母和数字。"""
    if len(pw) < 8:
        raise HTTPException(400, "密码至少 8 位")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"[0-9]", pw):
        raise HTTPException(400, "密码需包含字母和数字")


def validate_username(username: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username or ""):
        raise HTTPException(400, "用户名需为 3-32 位字母/数字/下划线/点/横线")


# ---------------- JWT ----------------
def _issue(user_id: int, perms: list) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    access = jwt.encode(
        {"sub": str(user_id), "perms": perms, "type": "access",
         "iat": now, "exp": now + timedelta(seconds=ACCESS_TTL)},
        JWT_SECRET, algorithm="HS256",
    )
    refresh = jwt.encode(
        {"sub": str(user_id), "type": "refresh",
         "iat": now, "exp": now + timedelta(seconds=REFRESH_TTL)},
        JWT_SECRET, algorithm="HS256",
    )
    return access, refresh


def _decode(token: str, want: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的登录态")
    if payload.get("type") != want:
        raise HTTPException(401, "无效的登录态")
    return payload


def _set_cookies(resp, access: str, refresh: str):
    resp.set_cookie("access_token", access, max_age=ACCESS_TTL, **COOKIE_KW)
    resp.set_cookie("refresh_token", refresh, max_age=REFRESH_TTL, **COOKIE_KW)


def _clear_cookies(resp):
    resp.delete_cookie("access_token", path="/")
    resp.delete_cookie("refresh_token", path="/")


# ---------------- 数据访问 ----------------
def _user_perms(cur, user_id: int) -> list:
    cur.execute(
        """SELECT DISTINCT p.key FROM permissions p
           JOIN role_permissions rp ON rp.permission_id = p.id
           JOIN user_roles ur ON ur.role_id = rp.role_id
           WHERE ur.user_id = %s""",
        (user_id,),
    )
    return sorted(r[0] for r in cur.fetchall())


def _user_roles(cur, user_id: int) -> list:
    cur.execute(
        """SELECT r.name FROM roles r
           JOIN user_roles ur ON ur.role_id = r.id
           WHERE ur.user_id = %s""",
        (user_id,),
    )
    return sorted(r[0] for r in cur.fetchall())


def _grant_role(cur, user_id: int, role_name: str):
    cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(500, f"角色不存在：{role_name}")
    cur.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (user_id, row[0]),
    )


def _public_user(row) -> dict:
    # row: id, username, email, display_name, is_active, created_at
    return {
        "id": row[0], "username": row[1], "email": row[2],
        "display_name": row[3], "is_active": row[4],
    }


# ---------------- 依赖：当前用户 / 权限 ----------------
def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "未登录")
    payload = _decode(token, "access")
    user_id = int(payload["sub"])
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, display_name, is_active, created_at"
            " FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if not row or not row[4]:
            raise HTTPException(401, "用户不存在或已禁用")
        user = _public_user(row)
        user["permissions"] = payload.get("perms") or _user_perms(cur, user_id)
        user["roles"] = _user_roles(cur, user_id)
    return user


def require_perm(perm: str):
    """权限守卫：用户权限点须包含 perm（admin 角色天然拥有全部权限点）。"""
    def _check(user: dict = Depends(get_current_user)) -> dict:
        if perm not in user["permissions"]:
            raise HTTPException(403, f"缺少权限：{perm}")
        return user
    return _check


# 供 main.py lifespan 调用的 admin 种子
def ensure_admin_seed():
    admin_user = os.environ.get("ADMIN_USER", "")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "")
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "sql", "schema_auth.sql")
    with _conn() as conn, conn.cursor() as cur:
        # 建表 + 种子角色权限（幂等）
        if os.path.exists(schema_path):
            cur.execute(open(schema_path, encoding="utf-8").read())
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] > 0:
            return
        if not admin_user or not admin_pass:
            log.warning("users 表为空且未配置 ADMIN_USER/ADMIN_PASSWORD，跳过 admin 初始化")
            return
        validate_password(admin_pass)
        cur.execute(
            "INSERT INTO users (username, password_hash, display_name)"
            " VALUES (%s, %s, %s) RETURNING id",
            (admin_user, hash_password(admin_pass), admin_user),
        )
        uid = cur.fetchone()[0]
        _grant_role(cur, uid, "admin")
        log.info("已创建初始管理员：%s", admin_user)
        # 旧单用户时代的自选股（user_id='default'）划归 admin
        try:
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'watchlist'")
            if cur.fetchone():
                cur.execute("UPDATE watchlist SET user_id = %s WHERE user_id = 'default'",
                            (admin_user,))
                if cur.rowcount:
                    log.info("已将 %d 条旧自选股迁移给 %s", cur.rowcount, admin_user)
        except Exception as exc:  # noqa: BLE001
            log.warning("迁移旧自选股失败：%s", exc)


# ---------------- 模型 ----------------
class RegisterIn(BaseModel):
    username: str
    password: str
    display_name: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


# ---------------- 接口 ----------------
@router.post("/api/auth/register")
def register(body: RegisterIn):
    """开放注册：默认 viewer 角色。"""
    validate_username(body.username)
    validate_password(body.password)
    display = (body.display_name or body.username).strip()[:64]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s", (body.username,))
        if cur.fetchone():
            raise HTTPException(400, "用户名已存在")
        cur.execute(
            "INSERT INTO users (username, password_hash, display_name)"
            " VALUES (%s, %s, %s) RETURNING id",
            (body.username, hash_password(body.password), display),
        )
        uid = cur.fetchone()[0]
        _grant_role(cur, uid, "viewer")
        perms = _user_perms(cur, uid)
    from fastapi.responses import JSONResponse
    access, refresh = _issue(uid, perms)
    resp = JSONResponse({"id": uid, "username": body.username,
                         "display_name": display, "permissions": perms,
                         "roles": ["viewer"]})
    _set_cookies(resp, access, refresh)
    return resp


@router.post("/api/auth/login")
def login(body: LoginIn):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, display_name, is_active, created_at, password_hash"
            " FROM users WHERE username = %s",
            (body.username,),
        )
        row = cur.fetchone()
        if not row or not row[4] or not row[6] or not verify_password(body.password, row[6]):
            raise HTTPException(401, "用户名或密码错误")
        user = _public_user(row)
        user["permissions"] = _user_perms(cur, row[0])
        user["roles"] = _user_roles(cur, row[0])
    from fastapi.responses import JSONResponse
    access, refresh = _issue(user["id"], user["permissions"])
    resp = JSONResponse(user)
    _set_cookies(resp, access, refresh)
    return resp


@router.post("/api/auth/logout")
def logout():
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    _clear_cookies(resp)
    return resp


@router.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/api/auth/refresh")
def refresh(request: Request):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "未登录")
    payload = _decode(token, "refresh")
    user_id = int(payload["sub"])
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT is_active FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(401, "用户不存在或已禁用")
        perms = _user_perms(cur, user_id)
    from fastapi.responses import JSONResponse
    access, new_refresh = _issue(user_id, perms)
    resp = JSONResponse({"ok": True})
    _set_cookies(resp, access, new_refresh)
    return resp


# ---------------- Google OAuth ----------------
def _google_redirect_uri(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/auth/google/callback"


@router.get("/api/auth/google/login")
def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "未配置 GOOGLE_CLIENT_ID")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


@router.get("/api/auth/google/callback")
def google_callback(request: Request, code: str = "", error: str = ""):
    if error:
        raise HTTPException(400, f"Google 授权失败：{error}")
    if not code:
        raise HTTPException(400, "缺少授权码")
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(500, "未配置 Google OAuth")
    # code 换 token
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": _google_redirect_uri(request),
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            tok = __import__("json").load(r)
    except Exception as exc:
        raise HTTPException(502, f"Google token 交换失败：{exc}")
    access_token = tok.get("access_token")
    if not access_token:
        raise HTTPException(502, "Google 未返回 access_token")
    # 取用户信息
    req2 = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req2, timeout=15) as r:
            info = __import__("json").load(r)
    except Exception as exc:
        raise HTTPException(502, f"获取 Google 用户信息失败：{exc}")
    sub = info.get("sub")
    email = info.get("email", "")
    name = info.get("name") or email.split("@")[0] or "google用户"
    if not sub:
        raise HTTPException(502, "Google 未返回用户标识")

    with _conn() as conn, conn.cursor() as cur:
        # 1) 按 google_sub 找
        cur.execute(
            "SELECT id, username, email, display_name, is_active, created_at"
            " FROM users WHERE google_sub = %s", (sub,))
        row = cur.fetchone()
        if not row and email:
            # 2) 按 email 找已存在用户并绑定
            cur.execute(
                "SELECT id, username, email, display_name, is_active, created_at"
                " FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE users SET google_sub = %s WHERE id = %s",
                            (sub, row[0]))
        if not row:
            # 3) 自动创建（viewer 角色）
            username = (email.split("@")[0] or f"g{sub[-6:]}")[:32]
            base_username = username
            i = 0
            while True:
                cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
                if not cur.fetchone():
                    break
                i += 1
                username = f"{base_username}{i}"[:32]
            cur.execute(
                "INSERT INTO users (username, google_sub, email, display_name)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                (username, sub, email, name[:64]),
            )
            uid = cur.fetchone()[0]
            _grant_role(cur, uid, "viewer")
            cur.execute(
                "SELECT id, username, email, display_name, is_active, created_at"
                " FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
        if not row[4]:
            raise HTTPException(403, "用户已禁用")
        user = _public_user(row)
        user["permissions"] = _user_perms(cur, row[0])
        user["roles"] = _user_roles(cur, row[0])
    access, refresh = _issue(user["id"], user["permissions"])
    resp = RedirectResponse("/")
    _set_cookies(resp, access, refresh)
    return resp


# ---------------- 用户管理（admin） ----------------
class UserCreate(BaseModel):
    username: str
    password: str = ""
    display_name: str = ""
    roles: list = []


@router.get("/api/users")
def list_users(_: dict = Depends(require_perm("users:manage"))):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, display_name, is_active, created_at,"
            " password_hash IS NOT NULL AS has_password,"
            " google_sub IS NOT NULL AS has_google"
            " FROM users ORDER BY id")
        users = []
        for r in cur.fetchall():
            users.append({
                "id": r[0], "username": r[1], "email": r[2],
                "display_name": r[3], "is_active": r[4],
                "created_at": r[5].isoformat() if r[5] else None,
                "has_password": r[6], "has_google": r[7],
                "roles": _user_roles(cur, r[0]),
            })
    return users


@router.post("/api/users")
def create_user(body: UserCreate, _: dict = Depends(require_perm("users:manage"))):
    validate_username(body.username)
    if body.password:
        validate_password(body.password)
    display = (body.display_name or body.username).strip()[:64]
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s", (body.username,))
        if cur.fetchone():
            raise HTTPException(400, "用户名已存在")
        cur.execute(
            "INSERT INTO users (username, password_hash, display_name)"
            " VALUES (%s, %s, %s) RETURNING id",
            (body.username,
             hash_password(body.password) if body.password else None,
             display),
        )
        uid = cur.fetchone()[0]
        for rn in body.roles or ["viewer"]:
            _grant_role(cur, uid, rn)
    return {"id": uid}


@router.put("/api/users/{user_id}")
def update_user(user_id: int, body: dict, _: dict = Depends(require_perm("users:manage"))):
    with _conn() as conn, conn.cursor() as cur:
        if "is_active" in body:
            cur.execute("UPDATE users SET is_active = %s WHERE id = %s",
                        (bool(body["is_active"]), user_id))
        if body.get("password"):
            validate_password(body["password"])
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                        (hash_password(body["password"]), user_id))
        if "display_name" in body:
            cur.execute("UPDATE users SET display_name = %s WHERE id = %s",
                        (str(body["display_name"])[:64], user_id))
        if "roles" in body:
            cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            for rn in body["roles"] or []:
                _grant_role(cur, user_id, rn)
    return {"ok": True}


@router.get("/api/roles")
def list_roles(_: dict = Depends(require_perm("users:manage"))):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, description FROM roles ORDER BY id")
        roles = [{"id": r[0], "name": r[1], "description": r[2]} for r in cur.fetchall()]
        cur.execute("""SELECT r.name, p.key FROM role_permissions rp
                       JOIN roles r ON r.id = rp.role_id
                       JOIN permissions p ON p.id = rp.permission_id""")
        perms = {}
        for rn, pk in cur.fetchall():
            perms.setdefault(rn, []).append(pk)
        cur.execute("SELECT key, description FROM permissions ORDER BY id")
        all_perms = [{"key": r[0], "description": r[1]} for r in cur.fetchall()]
    return {"roles": roles, "role_permissions": perms, "permissions": all_perms}


@router.put("/api/roles/{role_name}/permissions")
def set_role_permissions(role_name: str, body: dict,
                         _: dict = Depends(require_perm("users:manage"))):
    keys = body.get("permissions") or []
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "角色不存在")
        rid = row[0]
        cur.execute("DELETE FROM role_permissions WHERE role_id = %s", (rid,))
        for k in keys:
            cur.execute("SELECT id FROM permissions WHERE key = %s", (k,))
            prow = cur.fetchone()
            if prow:
                cur.execute(
                    "INSERT INTO role_permissions (role_id, permission_id)"
                    " VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (rid, prow[0]))
    return {"ok": True}
