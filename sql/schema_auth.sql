-- ============================================================
-- 认证与权限：用户 / 角色 / 权限（RBAC）
-- 幂等：可重复执行
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,   -- 登录名
    password_hash TEXT,                  -- bcrypt；纯 Google 登录用户为 NULL
    google_sub    TEXT UNIQUE,           -- Google OIDC sub
    email         TEXT,
    display_name  TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_google_sub ON users (google_sub) WHERE google_sub IS NOT NULL;

CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS permissions (
    id          SERIAL PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,    -- 如 market:view
    description TEXT
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- ---------------- 种子：权限点 ----------------
INSERT INTO permissions (key, description) VALUES
    ('market:view', '市场概览'),
    ('quotes:view', '行情 / 个股 / K线'),
    ('screener:use', '策略选股'),
    ('watchlist:use', '自选股'),
    ('extra:view', '市场深度'),
    ('weeks:download', '周文件下载'),
    ('sync:view', '数据更新查看'),
    ('sync:run', '触发数据回填'),
    ('users:manage', '用户管理'),
    ('files:view', '文件查看 / 下载'),
    ('files:upload', '文件上传'),
    ('files:manage', '文件删除管理'),
    ('blog:view', '博客查看'),
    ('blog:manage', '博客写作 / 发布 / 删除'),
    ('gallery:view', '相册查看'),
    ('gallery:upload', '相册新建 / 照片上传'),
    ('gallery:manage', '相册删除管理'),
    ('game:view', '游戏 / 排行榜'),
    ('tools:use', '工具箱'),
    ('news60s:view', '60秒新闻查看'),
    ('news60s:sync', '60秒新闻同步 / 统计')
ON CONFLICT (key) DO NOTHING;

-- ---------------- 种子：角色 ----------------
INSERT INTO roles (name, description) VALUES
    ('admin', '管理员：全部权限'),
    ('operator', '运维：除用户管理外全部权限'),
    ('viewer', '只读：市场概览 / 行情 / 市场深度 / 周文件下载 / 文件查看 / 博客 / 相册 / 游戏 / 60秒新闻')
ON CONFLICT (name) DO NOTHING;

-- ---------------- 种子：角色-权限 ----------------
-- admin：全部
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

-- operator：除 users:manage 外全部
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name = 'operator' AND p.key <> 'users:manage'
ON CONFLICT DO NOTHING;

-- viewer：只读九项
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name = 'viewer'
  AND p.key IN ('market:view', 'quotes:view', 'extra:view', 'weeks:download',
                'files:view', 'blog:view', 'gallery:view', 'game:view', 'tools:use',
                'news60s:view')
ON CONFLICT DO NOTHING;
