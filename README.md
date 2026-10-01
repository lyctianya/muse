# 股票数据管道

自建 A股 / 港股 / 美股 日线行情库：定时拉取（前复权）→ PostgreSQL →
每周打包 Parquet → GitHub Releases 公开发布 → 用户用 merger 工具按需合并。

数据源：A股（东方财富 via AkShare，主）/ yfinance（校验兜底）；
港股（腾讯行情 + yfinance）；美股（Stooq 主 + yfinance 备）。
名单尽量覆盖现役股票与 ETF（含 ST/*ST）；退市股以后续数据源能识别的为准，
不作绝对保证。当前全量约 3250 万行（A股 1031 万 / 港股 447 万 / 美股 1775 万）。

## 目录结构

```
.
├── docker-compose.yml        # db / fetcher / api 三服务编排
├── .env / .env.example       # 配置（.env 不提交）
├── fetcher/                  # 拉取端：Python + APScheduler
│   ├── config.py / db.py     # 配置 / 连接池 + upsert
│   ├── sources/cn.py         # A股（AkShare + 前复权校验 + yfinance 兜底）
│   ├── sources/cn_fundamentals.py  # A股基本面（公司/财务/股东，近2年）
│   ├── sources/hk.py         # 港股（腾讯 + yfinance）
│   ├── sources/us.py         # 美股（Stooq 主 + yfinance 备）
│   ├── jobs/backfill.py      # 历史回填（断点续跑）
│   ├── jobs/backfill_fundamentals.py  # 基本面回填（A股近2年）
│   ├── jobs/daily_fetch.py   # 每日增量拉取
│   ├── jobs/weekly_export.py # 周导出 Parquet + GitHub Release 发布
│   └── scheduler.py          # 调度器入口
├── api/                      # FastAPI 查询接口 + 前端托管
├── web/                      # Vue 3 + Vite + Arco Design + ECharts 前端
│   ├── public/folio/         # Folio 3D 静态资源（体积大；Docker/CI 需足够磁盘）
│   └── src/modules/folio/    # Bruno folio 引擎（公开首页 `/`）
│       └── …/HubView.vue     # 挂载 Folio；业务路由仍走登录与权限
├── merger/                   # 用户侧独立合并工具
├── scripts/                  # 本机工具（如全量 Parquet 导入）
├── sql/schema.sql            # 建表语句（行情）
└── sql/schema_fundamentals.sql  # 建表语句（基本面，10 张表）
```

## 使用方法

### 1. 本机原生运行（无 Docker）

#### 依赖安装（全部步骤）

**0) 系统前置（本机已装可跳过）**

| 组件 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.12+ | API / fetcher / merger |
| Node.js | 24+（含 npm） | 前端 `web/` |
| PostgreSQL | 18 | 行情库 `stocks` |

确认：

```bash
python --version    # 或 python3 --version
node --version
npm --version
psql --version
```

**1) 配置 `.env`**

```bash
# 项目根目录
cp .env.example .env
# 编辑 .env：至少填写 POSTGRES_PASSWORD 与 DATABASE_URL
# 示例：DATABASE_URL=postgresql://stockapp:你的密码@127.0.0.1:5432/stocks
```

**2) 创建库与表（PostgreSQL）**

需已有数据库 `stocks`、用户 `stockapp`（密码与 `.env` 一致）。首次：

```bash
# Linux / macOS（读取 .env 中的 DATABASE_URL）
set -a && source .env && set +a
psql "$DATABASE_URL" -f sql/schema.sql

# Windows PowerShell 示例
$env:PGPASSWORD = 'postgres'
psql -U stockapp -h 127.0.0.1 -p 5432 -d stocks -f sql/schema.sql
psql -U stockapp -h 127.0.0.1 -p 5432 -d stocks -f sql/schema_sync_status.sql
```

同步水位表 `sync_status`：记录各业务表最新日期/行数，前端「数据更新」页与
增量回填起点以此为准（避免每次扫业务表做 `COUNT/MAX`）。建表后初始化：

```bash
.venv/bin/python -m fetcher.jobs.refresh_sync_status          # Linux / macOS
.\.venv\Scripts\python -m fetcher.jobs.refresh_sync_status    # Windows
```

**3) Python 虚拟环境 + 后端依赖**

在项目根目录安装 **API + fetcher**（日常跑前后端 / 调度器必装）：

```bash
python -m venv .venv

# Linux / macOS
.venv/bin/pip install -U pip
.venv/bin/pip install -r fetcher/requirements.txt -r api/requirements.txt

# Windows PowerShell
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r fetcher/requirements.txt -r api/requirements.txt
```

对应清单：

- [`api/requirements.txt`](api/requirements.txt)：FastAPI、uvicorn、psycopg
- [`fetcher/requirements.txt`](fetcher/requirements.txt)：AkShare、yfinance、pandas、pyarrow、APScheduler 等

按需另装（非启动前后端所必需）：

```bash
# 合并 GitHub Releases 周包
.venv/bin/pip install -r merger/requirements.txt          # Linux / macOS
.\.venv\Scripts\pip install -r merger/requirements.txt    # Windows

# 导入 sqldata 全量 Parquet（scripts/import_full_parquet.py）
# 依赖与 merger 重叠，装过 merger 或 fetcher 即可；若最小环境可：
.venv/bin/pip install "psycopg[binary]" pyarrow pandas
```

**4) 前端依赖（Node）**

```bash
cd web
npm install
cd ..
```

安装 `package.json` 中的 Vue 3、Vite 7、Arco Design、Three（钉死 `0.183.2`，与 Folio TSL 对齐）、Rapier 等。
`web/.npmrc` 已启用 `legacy-peer-deps`（`vite-plugin-node-polyfills` peer 范围与 Vite 7/8 不完全一致）。

公开首页 `/` 为 Folio 3D 世界（无需登录）；进入 `/market` 等业务路由时再鉴权。
环境变量见 `web/.env.example`（`VITE_COMPRESSED`、`VITE_FORCE_WEBGL` 等）。
静态资源在 `web/public/folio/`（含 Draco/Basis/模型/音效），体积较大，clone/Docker 构建请预留磁盘与内存。

可选：构建静态产物，供后端同端口托管：

```bash
cd web && npm run build && cd ..
```

Docker 镜像构建（`api/Dockerfile`）会执行 `npm run build` 并打包 `public/folio`；若 OOM，请加大构建机内存。
**5) 安装结果自检（可选）**

```bash
# Linux / macOS
.venv/bin/python -c "import fastapi, uvicorn, psycopg, akshare, pandas; print('python ok')"

# Windows PowerShell
.\.venv\Scripts\python -c "import fastapi, uvicorn, psycopg, akshare, pandas; print('python ok')"

cd web && npm ls --depth=0 && cd ..
psql "$DATABASE_URL" -c "\dt"    # 应看到 symbols / daily_bars / ingested_weeks
```

#### 启动后端（API）

另开终端，在项目根目录：

```bash
# Linux / macOS
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Windows PowerShell
.\.venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

- 地址：`http://localhost:8000`
- 接口前缀：`/api`（如 `/api/health`、`/api/symbols`、`/api/bars`）
- 若已执行过 `cd web && npm run build`，同一端口还会托管前端静态页（`web/dist`）

#### 启动前端（开发模式）

后端保持运行，再开一个终端：

```bash
cd web
npm run dev
```

- 地址：`http://localhost:5173`
- Vite 已将 `/api` 代理到 `http://localhost:8000`，改前端代码可热更新

生产式一体访问（不跑 Vite）：先 `cd web && npm run build`，再只启动后端，浏览器打开 `http://localhost:8000`。

#### 可选：拉取调度器

```bash
# Linux / macOS
.venv/bin/python -m fetcher.scheduler

# Windows PowerShell
.\.venv\Scripts\python -m fetcher.scheduler

# 手动触发一次（冒烟 / 补跑，不启动定时循环）
.venv/bin/python -m fetcher.scheduler --run-now daily --market cn
.venv/bin/python -m fetcher.scheduler --run-now weekly
```

每天 05:30 自动增量拉取；每周一 06:10 自动导出 Parquet 并发布 Release。

### 2. Docker 部署（任意服务器）

```bash
# 项目根目录
cp .env.example .env   # 填写 POSTGRES_PASSWORD / GITHUB_TOKEN / GITHUB_REPO
docker compose up -d --build
# API: http://<服务器>:8000
# 首次启动自动全历史回填，之后按定时任务增量运行
```

### 3. 历史回填（首次建库）

```bash
# 回填近 10 年日线（2016-09-26 起），支持断点续跑，中断后重跑自动跳过已完成的
.venv/bin/python -m fetcher.jobs.backfill --market cn --start 2016-09-26 --workers 4
.venv/bin/python -m fetcher.jobs.backfill --market hk --start 2016-09-26 --workers 4
.venv/bin/python -m fetcher.jobs.backfill --market us --start 2016-09-26 --workers 6

# --market 可选 cn / hk / us；--workers 为并发数
# 日志在 logs/backfill_<market>.log；进度每 200 只打印一次
```

### 4. 查数据：API 接口

| 接口 | 说明 | 示例 |
|---|---|---|
| `GET /api/symbols?market=cn&q=茅台` | 搜索股票（market: cn/hk/us） | `/api/symbols?market=us&q=AAPL` |
| `GET /api/bars?market=cn&symbol=600519&from=2026-01-01&to=2026-09-26` | K 线（前复权日线） | `/api/bars?market=hk&symbol=00700&from=2020-01-01` |
| `GET /api/weeks` | 已发布的周数据包列表 | — |
| `GET /api/health` | 健康检查 | — |

前端页面（`http://localhost:8000`）提供搜索 + K 线图表（ECharts），开箱即用。

### 5. 查数据：直接连数据库

```sql
-- 某只股票近 10 年日线（前复权）
SELECT trade_date, open, high, low, close, volume
FROM daily_bars
WHERE market = 'cn' AND symbol = '600519'
ORDER BY trade_date;

-- 各市场数据量
SELECT market, COUNT(*), COUNT(DISTINCT symbol),
       MIN(trade_date), MAX(trade_date)
FROM daily_bars GROUP BY market;

-- 搜索股票
SELECT symbol, name FROM symbols WHERE market = 'hk' AND name LIKE '%腾讯%';
```

表结构见 `sql/schema.sql`。`daily_bars` 主键为 `(market, symbol, trade_date)`，
价格已做前复权（以最新交易日为锚）。

### 6. 取数据：GitHub Releases 周包（无需跑库）

每周一自动发布，附件为三市场的周 Parquet（`cn-2026-W39.parquet` 等）
加 `manifest.json`。公开仓库下载无需鉴权，直接在 Releases 页面下载，
或用 merger 工具一键入库（见下）。

### 6b. 全量 Parquet 一次性入库（新库初始化）

从 Release `data-2026-09-26-full` 下载三个 `*-full.parquet`，
放到项目根的 `sqldata/` 目录（或任意目录，用 `--dir` 指定），然后：

```bash
# Linux / macOS
.venv/bin/python scripts/import_full_parquet.py
# Windows PowerShell
.\.venv\Scripts\python scripts/import_full_parquet.py

# 只导港股 / 指定目录 / 指定数据库
.venv/bin/python scripts/import_full_parquet.py --market hk --dir D:\data --db postgresql://user:pass@127.0.0.1:5432/stocks
```

说明：按 Parquet row group 分批 `COPY` 入暂存表再 `MERGE`，
主键冲突自动更新；导入前后自动重建索引并回填 `symbols` 表。

### 7. 合并工具（用户侧，把 Release 数据灌进自己的库）

```bash
pip install -r merger/requirements.txt

# 合并某仓库的全部周数据到本地库
python merger/merger.py --repo lyctianya/muse --db postgresql://user:pass@localhost:5432/stocks

# 只合并指定周
python merger/merger.py --repo lyctianya/muse --db postgresql://user:pass@localhost:5432/stocks --week 2026-W39

# --db 缺省时读取 DATABASE_URL 环境变量
export DATABASE_URL=postgresql://user:pass@localhost:5432/stocks
python merger/merger.py --repo lyctianya/muse
```

说明：本地 `ingested_weeks` 表记录已入库的周，重复运行自动跳过；
入库用 `COPY` 极速写入，主键冲突自动降级为 `ON CONFLICT DO UPDATE`；
Parquet 是通用格式，不用本工具也能导入 DuckDB / SQLite 等。

## 接口一览

| 接口 | 说明 |
|---|---|
| `GET /api/symbols?market=cn&q=茅台` | 搜索股票 |
| `GET /api/bars?market=cn&symbol=600519&from=2026-01-01&to=2026-09-26` | K 线数据 |
| `GET /api/weeks` | 周文件列表 |
| `GET /api/health` | 健康检查 |
| `GET /api/company?symbol=600519` | 公司基本信息（行业/PE/PB/市值，A股） |
| `GET /api/financials?symbol=600519&type=income` | 财务三表/指标（type=income/balance/cashflow/indicator） |
| `GET /api/business?symbol=600519` | 主营业务构成 |
| `GET /api/holders?symbol=600519&type=top10` | 前十大股东（type=top10/float10） |
| `GET /api/pledge?symbol=600519` | 股权质押 |
| `GET /api/holder-numbers?symbol=600519` | 股东人数历史 |
| `GET /api/holder-trades?symbol=600519` | 股东增减持 |
| `GET /api/tech?market=cn&symbol=600519&from=2026-01-01&to=2026-09-26&indicator=macd` | 技术指标（macd/kdj/boll，本地计算） |

### 8. A股基本面数据（近 2 年）

基本面表结构见 `sql/schema_fundamentals.sql`（10 张表：公司信息、财务三表、
财务指标、主营构成、十大股东、质押、股东人数、增减持）。

```bash
# 1) 建表
set -a && source .env && set +a
psql "$DATABASE_URL" -f sql/schema_fundamentals.sql

# 2) 回填（A股现役名单，近 2 年；沙箱网络不通，需在本机跑）
.venv/bin/python -m fetcher.jobs.backfill_fundamentals --limit 5   # 先拿 5 只冒烟
.venv/bin/python -m fetcher.jobs.backfill_fundamentals             # 全量

# 3) 前端查看：搜索页点某只 A股 的「基本面」按钮，或直接访问
#    http://127.0.0.1:5173/company/600519
```

前端公司详情页含：基本信息（PE/PB/市值/行业）、K线+MACD、
财务三表/指标、主营业务、十大股东、股东增减持。

## 注意事项

- `.env` 含真实密码，已 gitignore，**绝不提交、绝不写进文档**
- 全历史回填数据量大（A股+港股+美股约 3250 万行），磁盘不足时不要在小机器上跑
- 免费数据源（AkShare/东方财富/腾讯/Stooq/yfinance）有频率限制，
  代码内置重试 + 退避 + 降级；A股前复权数据做批量合理性校验，
  坏行比例超 5% 时自动切 yfinance 重抓
- A股名单优先用 24h 本地缓存（`fetcher/.cache/cn_symbols.json`），
  交易所官网抽风时不阻塞回填

## 运维备注（本机沙箱）

- 本机根分区（overlay，7.5G）**重启会被重置**：apt 安装的 postgresql-18、
  postgres 系统用户、apt 源修改等都不持久。`/home/hatch` 是 100G 独立持久盘，
  重启不受影响；项目代码、`.env`、PostgreSQL 数据目录都在上面。
- PostgreSQL 数据目录：**`/home/hatch/pgdata`**（持久盘），不要用默认的
  `/var/lib/postgresql`（根分区太小，10 年回填装不下）。
- 重启后一键恢复（重装 PG 18 + 启动数据库，数据完好无需重建）：
  ```bash
  bash /home/hatch/pg_recover.sh
  ```
  脚本做了幂等处理，可重复执行。回填任务支持断点续跑，重启后重跑即可。
- 将来迁移到正式服务器建议改用 Docker 方案，不再需要上述 workaround。
