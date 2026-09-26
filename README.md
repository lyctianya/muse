# 股票数据管道

自建 A股 / 港股 / 美股 日线行情库：定时拉取（前复权）→ PostgreSQL →
每周打包 Parquet → GitHub Releases 公开发布 → 用户用 merger 工具按需合并。

数据源：A股（东方财富 via AkShare，主）/ yfinance（校验兜底）；
港股（腾讯行情 + yfinance）；美股（Stooq 主 + yfinance 备）。
含退市过滤（剔除退市）、保留 ST/*ST，股票与 ETF 都要。

## 目录结构

```
stock-data/
├── docker-compose.yml        # db / fetcher / api 三服务编排
├── .env / .env.example       # 配置（.env 不提交）
├── fetcher/                  # 拉取端：Python + APScheduler
│   ├── config.py / db.py     # 配置 / 连接池 + upsert
│   ├── sources/cn.py         # A股（AkShare + 前复权校验 + yfinance 兜底）
│   ├── sources/hk.py         # 港股（腾讯 + yfinance）
│   ├── sources/us.py         # 美股（Stooq 主 + yfinance 备）
│   ├── jobs/backfill.py      # 历史回填（断点续跑）
│   ├── jobs/daily_fetch.py   # 每日增量拉取
│   ├── jobs/weekly_export.py # 周导出 Parquet + GitHub Release 发布
│   └── scheduler.py          # 调度器入口
├── api/                      # FastAPI 查询接口 + 前端托管
├── web/                      # Vue 3 + Vite + Arco Design + ECharts 前端
├── merger/                   # 用户侧独立合并工具
└── sql/schema.sql            # 建表语句
```

## 使用方法

### 1. 本机原生运行（无 Docker）

前置：Python 3.12、Node 24+、PostgreSQL 18（库 `stocks`、账号 `stockapp`）。

```bash
cd stock-data

# 1) Python 环境
python3 -m venv .venv
.venv/bin/pip install -r fetcher/requirements.txt -r api/requirements.txt

# 2) 建表（DATABASE_URL 从 .env 读取）
set -a && source .env && set +a
psql "$DATABASE_URL" -f sql/schema.sql

# 3) 前端构建
cd web && npm install && npm run build && cd ..

# 4) 启动 API（http://localhost:8000，/api 接口 + 前端页面）
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 5) 启动拉取调度器（另开终端）
.venv/bin/python -m fetcher.scheduler
# 每天 05:30 自动增量拉取；每周一 06:10 自动导出 Parquet 并发布 Release

# 手动触发一次（冒烟 / 补跑，不启动定时循环）
.venv/bin/python -m fetcher.scheduler --run-now daily --market cn
.venv/bin/python -m fetcher.scheduler --run-now weekly

# 前端开发模式（另开终端，/api 代理到本地 8000）
cd web && npm run dev   # http://localhost:5173
```

### 2. Docker 部署（任意服务器）

```bash
cd stock-data
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

## 注意事项

- `.env` 含真实密码，已 gitignore，**绝不提交、绝不写进文档**
- 全历史回填数据量大（A股+港股+美股约 1400 万行），磁盘不足时不要在小机器上跑
- 免费数据源（AkShare/东方财富/腾讯/Stooq/yfinance）有频率限制，
  代码内置重试 + 退避 + 降级；A股另有前复权逐行校验，坏数据自动切 yfinance
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
