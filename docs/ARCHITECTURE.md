# 架构总览（2026-09-29 模块化重构后）

单仓、模块化单体：一个 FastAPI 应用、一个 Vue SPA、一个 PostgreSQL，
代码按业务域分模块，共享能力下沉到 platform。

## 目录结构

```
stock-data/                      # 仓库根（GitHub: lyctianya/muse）
├── api/                         # 后端：FastAPI
│   ├── main.py                  # 瘦装配层：只注册路由，不写业务
│   ├── requirements.txt / Dockerfile
│   ├── platform/                # 共享底座
│   │   ├── deps.py              # 配置 / DB 连接池 / 路径常量（ROOT）
│   │   ├── auth.py              # 用户 / 角色 / 权限 / JWT / Google OAuth
│   │   ├── health.py            # /api/health
│   │   └── storage.py           # 文件存储：本地磁盘 + files 元数据表
│   └── modules/                 # 业务域
│       ├── stock/               # 股票域：routers/ 12 个子路由
│       │   └── __init__.py      # 域装配：include_router + 权限守卫
│       ├── files/               # 文件域：router.py（上传/列表/下载/删除）
│       ├── blog/                # 博客域：文章/标签（Markdown）
│       ├── gallery/             # 相册域：相册/照片（文件走平台存储）
│       ├── game/                # 游戏域：three.js 游戏 + 排行榜
│       ├── news60s/             # 60秒新闻：上游同步 + 按日查询
│       └── agent/               # 规划中（AI agent，留空位）
│
│   注：tools 工具箱是纯前端模块（v1 无需后端），只有 web/src/modules/tools/。
├── web/src/                     # 前端：Vue 3 SPA
│   ├── shell/                   # 壳：App.vue / main.js / router / 登录 / 用户管理
│   ├── platform/                # 共享：theme.css / utils(api,auth,date,echarts)
│   └── modules/
│       ├── stock/views/ + components/
│       ├── files/views/FilesView.vue
│       ├── blog/views/（列表/详情/编辑）
│       ├── gallery/views/（相册列表/相册详情）
│       └── game/views/GameView.vue + games/starfall.js
│       └── tools/views/ToolsView.vue + tools/（10 个纯前端小工具，见下）
├── fetcher/                     # 股票域数据管道（独立 Docker 服务，暂不搬）
├── sql/schema_auth.sql          # 认证表 + 角色权限种子（幂等）
├── docs/                        # DESIGN.md / USAGE.md / 本文档
└── docker-compose.yml           # db + api（+ fetcher）
```

## 路由命名空间

| 前缀 | 说明 | 权限点 |
|---|---|---|
| `/api/auth/*`, `/api/users`, `/api/roles` | 平台认证 | 公开 / `users:manage` |
| `/api/health` | 健康检查 | 公开 |
| `/api/stock/*` | 股票域 | `market:view` 等 8 个 |
| `/api/files/*` | 文件域 | `files:view` / `files:upload` / `files:manage` |
| `/api/blog/*` | 博客域 | `blog:view` / `blog:manage` |
| `/api/gallery/*` | 相册域 | `gallery:view` / `gallery:upload` / `gallery:manage` |
| `/api/game/*` | 游戏域 | `game:view` |
| `/api/news60s/*` | 60秒新闻 | `news60s:view` / `news60s:sync` |

新域统一用 `/api/<domain>/*`。

## 数据库

单库，表按域前缀/注释区分。`files` 表存文件元数据，
实际文件在 `{STORAGE_ROOT}/{domain}/{yyyyMM}/{uuid}{ext}`（默认 `./data/files`）。

## 新模块接入规范

后端：
1. `api/modules/<domain>/` 建包，`router.py` 里写路由（路径不带 `/api` 前缀）。
2. `__init__.py` 导出 `router`（如需权限，在此 `include_router(..., dependencies=[...])`，
   参考 `api/modules/stock/__init__.py`）。
3. `api/main.py` 加一行 `app.include_router(<domain>_router, prefix="/api/<domain>")`。
4. 新权限点加到 `sql/schema_auth.sql` 种子（`ON CONFLICT DO NOTHING` 幂等；
   operator 用"除 users:manage 外全部"自动继承）。

前端：
1. `web/src/modules/<domain>/views/` 放页面，`components/` 放私有组件。
2. 共享工具只用 `web/src/platform/`（api/auth/date/echarts-theme/theme.css）。
3. `web/src/shell/router/index.js` 加路由（`meta.perm` 声明权限）。
4. `web/src/shell/App.vue` 加侧边栏菜单（`v-if="can('<perm>')"`）+ NAV 标题映射。

## 规划中的域

- **agent**：AI agent 系统（任务队列/执行日志/LLM Key 管理），复杂度高，
  等上述域落地后单独设计。

## 约定

- 跨域共享代码一律放 `api/platform/` 或 `web/src/platform/`，不许域之间直接 import。
- `fetcher/` 是股票域的数据管道，逻辑上属于 `modules/stock`，
  因改动面大暂留顶层，后续再搬。
