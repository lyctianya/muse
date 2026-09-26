# 股票数据管道

自建 A股 / 港股 / 美股 日线行情库：定时拉取（前复权）→ PostgreSQL →
每周打包 Parquet → GitHub Releases 公开发布 → 用户用 merger 工具按需合并。

详细技术方案见 `../TECH_SPEC.md`（任务文件夹归档）。

## 目录结构

```
stock-data/
├── docker-compose.yml        # db / fetcher / api 三服务编排
├── .env / .env.example       # 配置（.env 不提交）
├── fetcher/                  # 拉取端：Python + APScheduler
│   ├── config.py / db.py     # 配置 / 连接池 + upsert
│   ├── sources/cn.py         # A股（AkShare）
│   ├── sources/hk.py         # 港股（AkShare）
│   ├── sources/us.py         # 美股（Stooq 主 + yfinance 备）
│   ├── jobs/daily_fetch.py   # 每日拉取（含除权除息检测）
│   ├── jobs/weekly_export.py # 周导出 + GitHub Release 发布
│   └── scheduler.py          # 调度器入口
├── api/                      # FastAPI 查询接口 + 前端托管
├── web/                      # Vue 3 + Vite + Arco Design + ECharts 前端
├── merger/                   # 用户侧独立合并工具
└── sql/schema.sql            # 建表语句
```

## 本机原生运行（无 Docker）

前置：Python 3.12、Node 24+、PostgreSQL 18（库 `stocks`、账号 `stockapp`）。

```bash
cd stock-data

# 1. Python 环境
python3 -m venv .venv
.venv/bin/pip install -r fetcher/requirements.txt -r api/requirements.txt

# 2. 建表（DATABASE_URL 从 .env 读取）
set -a && source .env && set +a
psql "$DATABASE_URL" -f sql/schema.sql

# 3. 前端构建
cd web && npm install && npm run build && cd ..

# 4. 启动 API（http://localhost:8000，/api 接口 + 前端页面）
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 5. 启动拉取调度器（另开终端；每天 05:30 / 每周一 06:10 自动跑）
.venv/bin/python -m fetcher.scheduler

# 手动触发一次（冒烟/补跑，不启动定时循环）
.venv/bin/python -m fetcher.scheduler --run-now daily --market cn
.venv/bin/python -m fetcher.scheduler --run-now weekly

# 前端开发模式（另开终端，/api 代理到本地 8000）
cd web && npm run dev   # http://localhost:5173
```

## Docker 部署（任意服务器）

```bash
cd stock-data
cp .env.example .env   # 填写 POSTGRES_PASSWORD / GITHUB_TOKEN / GITHUB_REPO
docker compose up -d --build
# API: http://<服务器>:8000
# 首次启动自动全历史回填（约 30–60 分钟），之后按定时任务增量运行
```

## 合并工具（用户侧）

```bash
pip install -r merger/requirements.txt
python merger/merger.py --repo owner/repo --db postgresql://user:pass@host:5432/stocks
```
详见 `merger/README.md`。

## 接口一览

| 接口 | 说明 |
|---|---|
| `GET /api/symbols?market=cn&q=茅台` | 搜索股票 |
| `GET /api/bars?market=cn&symbol=600519&from=2026-01-01&to=2026-09-26` | K 线数据 |
| `GET /api/weeks` | 周文件列表（占位，待周导出接入） |
| `GET /api/health` | 健康检查 |

## 注意事项

- `.env` 含真实密码，已 gitignore，**绝不提交、绝不写进文档**
- 全历史回填数据量大，磁盘不足时不要在小机器上跑（见 TECH_SPEC）
- 免费数据源（AkShare/Stooq/yfinance）有频率限制，代码内置重试+退避+降级

## 运维备注（本机沙箱）

- 本机根分区（overlay，7.5G）**重启会被重置**：apt 安装的 postgresql-18、
  apt 源修改等系统级改动不持久。`/home/hatch` 是 100G 独立持久盘，重启不受影响。
- PostgreSQL 数据目录放在 **`/home/hatch/pgdata`**（持久盘），不要用默认的
  `/var/lib/postgresql`（根分区太小，10 年回填装不下）。
- 特殊点：`/home/hatch` 的 btrfs 挂载把文件属主 squash 为 root，
  postgres 用户无法在上面拥有文件。因此 postgres 通过 **user namespace**
  启动（见 `/home/hatch/pgshim/start-pg.sh`）：容器内 uid 103（postgres）
  映射到外层 uid 0，进程真实以非 root 运行，属主校验自然通过。
- 重启后恢复步骤：
  1. 重装 postgres：`dpkg -i ~/workspace/tasks/stock-data-pipeline/pg-debs/*.deb`
     （apt 的代理认证在本机坏了，不要指望 `apt install`）
  2. 启动数据库：`bash /home/hatch/pgshim/start-pg.sh`
     （数据目录完好，角色/库/表都在，无需重建）
- 将来迁移到正式服务器建议改用 Docker 方案（见 TECH_SPEC），不再需要上述 workaround。
