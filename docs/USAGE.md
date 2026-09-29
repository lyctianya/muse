# 股票数据管道 — 使用文档

> 配套：[设计文档](DESIGN.md)　　项目根目录以下简称 `<root>`

---

## 1. 环境要求

| 组件 | 版本 | 用途 |
|---|---|---|
| Python | 3.12+ | API / fetcher / merger / 脚本 |
| Node.js | 24+（含 npm） | 前端 `web/` |
| PostgreSQL | 18 | 数据库 `stocks` |
| `gh` CLI | 任意 | 发布 Release（可选） |
| `psql` / `pg_dump` | 随 PG 安装 | 建表 / 导出 schema |

---

## 2. 安装

```bash
git clone https://github.com/lyctianya/muse.git stock-data
cd stock-data

# 1) 配置
cp .env.example .env   # 填写 POSTGRES_PASSWORD / DATABASE_URL 等，见第 3 节

# 2) 建库建表（库 stocks 和用户 stockapp 需预先创建）
psql "$DATABASE_URL" -f sql/schema.sql                 # 行情
psql "$DATABASE_URL" -f sql/schema_fundamentals.sql    # 基本面
psql "$DATABASE_URL" -f sql/schema_tushare_extra.sql   # Tushare 增量
psql "$DATABASE_URL" -f sql/schema_tushare_full.sql    # Tushare 全量
psql "$DATABASE_URL" -f sql/schema_tushare_full2.sql
psql "$DATABASE_URL" -f sql/schema_tushare_full3.sql
psql "$DATABASE_URL" -f sql/schema_sync_status.sql     # 水位表
psql "$DATABASE_URL" -f sql/schema_watchlist.sql       # 自选股

# 3) Python 依赖
python -m venv .venv
.venv/bin/pip install -r fetcher/requirements.txt -r api/requirements.txt
# 合并工具（用户侧）按需：
.venv/bin/pip install -r merger/requirements.txt

# 4) 前端依赖（可选）
cd web && npm install && cd ..
```

Windows PowerShell 把 `.venv/bin/python` 换成 `.\.venv\Scripts\python`，`export` 换成 `$env:`。

---

## 3. 配置（`.env` / 环境变量）

```bash
DATABASE_URL=postgresql://stockapp:你的密码@127.0.0.1:5432/stocks
TUSHARE_TOKEN=你的Tushare token            # 走中转站时填平台 API Key
TUSHARE_BASE_URL=https://teajoin.com       # 直连官方请留空
GITHUB_TOKEN=ghp_xxx                        # weekly_export 自动发布用（可选）
GITHUB_REPO=lyctianya/muse                 # 发布目标仓库
TZ=Asia/Shanghai
```

`api` 启动时会自动加载 `<root>/.env`；fetcher 通过 `fetcher/config.py` 读取（环境变量优先）。

---

## 4. 首次回填（顺序建议）

### 4.1 行情日线（近10年，约3250万行，耗时最长先跑）

```bash
.venv/bin/python -m fetcher.jobs.backfill --market cn --start 2016-09-26
.venv/bin/python -m fetcher.jobs.backfill --market hk --start 2016-09-26
.venv/bin/python -m fetcher.jobs.backfill --market us --start 2016-09-26
```

或用 Release 全量包快速起步（见第 7 节 merger），再用 daily 增量追平。

### 4.2 Tushare 基本面（8 表）

```bash
export TUSHARE_TOKEN=<key> TUSHARE_BASE_URL=https://teajoin.com
.venv/bin/python -m fetcher.jobs.backfill_fundamentals --source tushare --check-token
.venv/bin/python -m fetcher.jobs.backfill_fundamentals --source tushare
```

### 4.3 Tushare 增量（6 表）

```bash
.venv/bin/python -m fetcher.jobs.backfill_tushare_extra          # 全部
.venv/bin/python -m fetcher.jobs.backfill_tushare_extra --only daily_basic
```

### 4.4 Tushare 全量（27 表）

```bash
# 先跑快的验证（指数信息、回购，几分钟）
.venv/bin/python -m fetcher.jobs.backfill_tushare_full --only index_info
.venv/bin/python -m fetcher.jobs.backfill_tushare_full --only repurchase
# 按日批量的先跑最近几天验证
.venv/bin/python -m fetcher.jobs.backfill_tushare_full --only hk_hold --from-date 2026-09-25
# 没问题再全量（逐只慢任务约 2.2 万次调用，按 450次/分约 1 小时+写入）
.venv/bin/python -m fetcher.jobs.backfill_tushare_full
```

Windows 一键脚本（自动 git pull + 建表 + 回填）：

```powershell
$env:TUSHARE_TOKEN="<key>"; $env:TUSHARE_BASE_URL="https://teajoin.com"
.\scripts\local_backfill_tushare_full.ps1 -Only index_info
.\scripts\local_backfill_tushare_full.ps1              # 全量
```

### 4.5 建水位

```bash
.venv/bin/python -m fetcher.jobs.refresh_sync_status
```

---

## 5. 日常运行

### 5.1 调度器（服务器）

```bash
.venv/bin/python -m fetcher.scheduler
# 每日 05:30 日线增量；每周一 06:10 导出上周日线并发布 Release
```

### 5.2 Windows 任务计划（个人电脑）

用 `scripts/setup_auto_update_task.ps1` 注册开机/定时任务，或参考 `scripts/daily_auto_update.ps1`。

### 5.3 /sync 页一键回填

启动 API（下节）后打开 `http://localhost:8000/sync`：看 44 张表的数据量/最新日期/
是否需更新，一键触发后台回填并看日志。

---

## 6. 启动 API + 前端

```bash
# 二选一：先构建前端（同端口托管），或 dev 模式联调
cd web && npm run build && cd ..
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000
```

---

## 7. 数据导出与发布

### 7.1 行情周包（自动）

`scheduler` 每周一 06:10 自动执行 `weekly_export`：导出上周 `daily_bars` 为
`exports/{cn,hk,us}-YYYY-Www.parquet` + `manifest-{week}.json`，有 `GITHUB_TOKEN` 则发布
`data-YYYY-Www` Release。

### 7.2 Tushare 基本面包（手动）

```bash
# 41 张表各一个 parquet + manifest.json + schema.sql，按保留策略裁剪后发布
.venv/bin/python scripts/export_tushare.py --tag tushare-2026-09-29
# 只导出不发布 / 只导某张表（调试）
.venv/bin/python scripts/export_tushare.py --tag tushare-2026-09-29 --no-release
.venv/bin/python scripts/export_tushare.py --tag x --table company_info --no-release --no-schema --out ./out
```

需要 `gh auth login`。同名 Release 已存在则跳过。

### 7.3 旧版基本面导出（遗留）

`scripts/export_fundamentals.py --tag fundamentals-YYYY-MM-DD`：只导东财时代 10 张表，
新库请用 7.2 代替。

---

## 8. 合并到本地库（merger，用户侧独立运行）

```bash
pip install -r merger/requirements.txt

# 行情：合并某仓库的全部周数据
python merger/merger.py --repo lyctianya/muse --db postgresql://user:pass@localhost:5432/stocks
# 只合指定周
python merger/merger.py --repo lyctianya/muse --db <连接串> --week 2026-W39

# 基本面：同时合并 tushare-YYYY-MM-DD Release（41 张表，先执行包内 schema.sql 建表）
python merger/merger.py --repo lyctianya/muse --db <连接串> --fundamentals
# 只合指定的基本面包
python merger/merger.py --repo lyctianya/muse --db <连接串> --fund-tag tushare-2026-09-29
```

说明：公开仓库附件下载无需鉴权；`--db` 缺省读 `DATABASE_URL`；已入库的周/tag 自动跳过，
全程幂等可重跑；下载缓存默认 `./merger-data`（`--data-dir` 可改）。

### 手动导入（不走 GitHub）

```bash
# Tushare 41 张表（先建表：psql -f Release中的schema.sql，或逐个执行 sql/schema_*.sql）
python scripts/import_tushare_parquet.py --dir ./tushare-data --db <连接串>
# 全量日线快照
python scripts/import_full_parquet.py --dir ./release --db <连接串>
```

---

## 9. API 速查

```bash
curl "http://localhost:8000/api/health"
curl "http://localhost:8000/api/symbols?market=cn&query=贵州茅台"
curl "http://localhost:8000/api/bars?market=cn&symbol=600519&from=2024-01-01&to=2026-09-29"
curl "http://localhost:8000/api/company?market=cn&symbol=600519"
curl "http://localhost:8000/api/financials?market=cn&symbol=600519&type=income"
curl "http://localhost:8000/api/holder-trades?market=cn&symbol=600519"
curl "http://localhost:8000/api/cyq?market=cn&symbol=600519&limit=60"
curl "http://localhost:8000/api/sync/status"
```

完整路由见 [设计文档](DESIGN.md) 第 5 节。

---

## 10. 前端页面指南

- `/` 市场概览：三市场涨跌家数、成交额、涨跌幅榜
- `/company/:symbol` 公司详情：K线 + 20+ tab（财务三表/指标、主营、股东、增减持、回购、
  质押、筹码、港股通持股、龙虎榜、两融、资金流、分红预告快报…），tab 懒加载
- `/extra` 市场深度：指数行情、龙虎榜、沪深港通资金、两融、IPO
- `/screener` 策略选股：字段条件 + 预设策略
- `/watchlist` 自选股分组管理；`/weeks` 周数据包下载；`/sync` 数据更新管理

---

## 11. 常见问题

| 现象 | 原因 / 解法 |
|---|---|
| Tushare 返回 40101 | token 过期；换 Key 或走中转站（`TUSHARE_BASE_URL`） |
| 中转站请求超时/被掐 | 沙箱出口 IP 被 WAF 拦截是已知限制，**请在本地跑**回填 |
| `daily_bars.pct_change` 为空/偏差大 | 跑 `python scripts/repair_pct_change.py --db <连接串>` |
| /sync 页水位不准 | `python -m fetcher.jobs.refresh_sync_status` 重建水位 |
| 回填中断 | 按日任务加 `--from-date` 断点续跑；逐只任务内部按 symbol 自动跳过已完成的 |
| merger 提示目标库无表 | 基本面合并前先执行 Release 包内 `schema.sql` 建表 |
| 导入 parquet 报列不匹配 | 导出/导入脚本按列名交集对齐，schema 漂移时会跳过缺失列并打 warning |
| Key 到期（如 DaoShare Key 2026-10-05 到期） | 到期前完成回填或续期；回填是幂等的，换 Key 后继续跑即可 |
