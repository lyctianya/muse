# 股票数据管道 — 项目设计文档

> 版本：2026-09-29　　对应代码：`main` 分支
> 配套文档：[使用文档](USAGE.md)　　原始方案：`~/workspace/tasks/stock-data-pipeline/TECH_SPEC.md`

---

## 1. 项目目标与范围

自建 **A股 / 港股 / 美股** 日线行情库 + **A股基本面库**（Tushare Pro）：

- 定时拉取三市场全量现役股票（含 ETF）**前复权日线**，PostgreSQL 落库
- A股基本面 / 资金流 / 事件数据（Tushare 41 张表）定时回填
- 数据以 **Parquet** 打包，通过 **GitHub Releases** 公开发布，用户用 merger 工具按需合并到本地库
- Web 前端：行情查询、公司详情（20+ 数据 tab）、策略选股、自选股、数据更新管理

**范围边界**：只做 A股（基本面及全部 Tushare 表均为 A股口径）；港股/美股仅行情日线；
不做实时分钟线、不做新闻/公告/研报全文、不做期货期权外汇。

---

## 2. 总体架构

```
                    ┌──────────────────────────────────────────────┐
                    │                   fetcher                     │
  AkShare(东财)     │  sources/cn.py ──▶                           │
  腾讯/yfinance     │  sources/hk.py ──▶  db.py(连接池+upsert) ──▶  │
  Stooq/yfinance    │  sources/us.py ──▶                           │   ┌────────┐
                    │  sources/tushare_*.py ──▶                   │   │Postgre │
  Tushare Pro       │   (fundamentals/extra/full 三模块)           │──▶│SQL 18  │◀── api ──▶ Web前端(Vue3)
  (官方/中转站)     │                                              │   │stocks  │   FastAPI
                    │  jobs/daily_fetch.py   (每日05:30 增量)      │   └────────┘
                    │  jobs/weekly_export.py (每周一06:10 导出)    │
                    └──────────────┬───────────────────────────────┘
                                   │ 每周导出 (Parquet+manifest)
                                   ▼
                    GitHub Releases ──▶ merger.py ──▶ 用户本地库
                    (data-YYYY-Www 行情周包 / tushare-YYYY-MM-DD 基本面包)
```

**运行形态**（两种，二选一）：

| 形态 | 组成 | 适用 |
|---|---|---|
| Docker Compose | `db` / `fetcher` / `api` 三服务（`api` 镜像内含 `web/dist`） | 服务器长期运行 |
| 本机原生 | PostgreSQL 本机 + `.venv` 跑 fetcher/api + `npm run dev/build` | Windows 个人电脑（当前主力） |

---

## 3. 数据模型

### 3.1 表清单（共 46 张）

| 组 | 表 | 说明 |
|---|---|---|
| 行情核心 | `symbols` | 三市场股票名单（现役，软删退市） |
| | `daily_bars` | 三市场前复权日线（~3250 万行） |
| | `ingested_weeks` | merger 已入库周登记 |
| 基本面·Tushare fundamentals（8） | `company_info` | 公司基本信息+估值快照 |
| | `fin_income` / `fin_balance` / `fin_cashflow` / `fin_indicator` | 财务三表+指标（VIP 季度批量） |
| | `top_holders` / `holder_number` / `pledge_info` | 十大股东/股东人数/质押统计 |
| 增量·Tushare extra（6） | `daily_basic` | 每日指标（PE/PB/市值/换手，近10年） |
| | `moneyflow` / `suspend` / `dividend` / `forecast` / `express` | 资金流/停复牌/分红/预告/快报 |
| 全量·Tushare full（15） | `fina_mainbz` / `company_detail` / `namechange` | 主营构成/公司详情/曾用名 |
| | `top_list` / `top_inst` | 龙虎榜+机构明细 |
| | `index_daily` / `moneyflow_hsgt` / `hsgt_top10` | 指数日线/沪深港通资金/十大成交股 |
| | `disclosure_date` / `margin` / `margin_detail` | 披露计划/两融汇总/两融明细 |
| | `stk_limit` / `fina_audit` / `new_share` / `managers` | 涨跌停/审计意见/IPO/管理层 |
| 全量2（2） | `share_float` / `block_trade` | 限售解禁/大宗交易 |
| 全量3（10） | `adj_factor` / `holder_trade` / `daily_ts` | 复权因子/股东增减持/Tushare日线 |
| | `repurchase` / `pledge_detail` | 股票回购/质押明细 |
| | `index_basic` / `index_weight` / `index_member` | 指数信息/权重/成分 |
| | `cyq_perf` / `hk_hold` | 每日筹码/沪深港股通持股 |
| 管理 | `sync_status` | 各表水位（最新日期/行数/同步时间） |
| | `watchlist` | 自选股 |

> `main_business`（东财旧表）已停用，`holder_trade` 已从东财口径迁移为 Tushare `stk_holdertrade` 口径。

### 3.2 数据保留策略

- **日线类**（`daily_bars` / `daily_basic` / `daily_ts` / `adj_factor` / `index_daily`）：近 **10 年**
- **其余**：近 **2 年**
- **维度表**（`company_detail` / `index_basic` / `index_member` / `new_share` / `company_info`）：全量
- 导出层（`export_tushare.py`）按此策略裁剪；抓取层按起止日期控制。

### 3.3 主键与幂等

全表 `INSERT ... ON CONFLICT (pk) DO UPDATE` 幂等写入，重跑安全。
典型主键：`(market, symbol, trade_date)`（日线类）、`(market, symbol, ann_date, …)`（事件类）。

---

## 4. 抓取子系统

### 4.1 行情抓取（`fetcher/sources/cn.py|hk.py|us.py`）

| 市场 | 名单源 | 日线源 | 前复权 | 兜底 |
|---|---|---|---|---|
| A股 | AkShare `stock_info_a_code_name` | 东财 `adjust="qfq"` | 源端直接给，`_sane()` 校验（坏行>5% 切源） | yfinance |
| 港股 | 港交所 xlsx → Yahoo 兜底 | yfinance `auto_adjust` | 源端 | — |
| 美股 | Nasdaq `nasdaqtraded.txt` | Stooq CSV | 源端 | yfinance |

- 除权检测：重叠日收盘价漂移超阈值（`ADJUST_SPLIT_THRESHOLD=0.5%`）则整股重拉
- `pct_change` 缺失时用前收补算；历史脏数据用 `scripts/repair_pct_change.py` 一次性修复
- `_tls_patch`：opt-in，把东财/北交所请求转给 curl_cffi（chrome124 指纹，30s 超时防 tar-pit）

### 4.2 Tushare 抓取（三模块）

| 模块 | 表数 | 文件 | 策略 |
|---|---|---|---|
| fundamentals | 8 | `tushare_fundamentals.py` | 财务走 `_vip` **季度批量**（近2年约32次调用）；股东/质押逐只并发 |
| extra | 6 | `tushare_extra.py` | **按交易日批量**（`daily_basic` 近10年约2430次调用）；`forecast`/`express` 按季度 |
| full | 27 | `tushare_full.py` | 批量优先：按交易日/公告日/指数；逐只兜底（`adj_factor`/`holdertrade`/`pledge_detail`/`cyq_perf` 约5500只×4） |

- 限流：`TUSHARE_MIN_INTERVAL=0.2s`（450次/分），并发 `TUSHARE_WORKERS=6`
- 中转站：`TUSHARE_BASE_URL` 为空直连官方，非空走中转（如 `https://teajoin.com`，token 填平台 API Key）；发往中转的请求自动带浏览器头（过 WAF）
- 断点续跑：`--from-date`（按日任务）/ 库内 max 日期 / 逐只任务内部按 symbol 跳过已追上

### 4.3 调度（`fetcher/scheduler.py`，APScheduler，Asia/Shanghai）

| 任务 | 时间 | 说明 |
|---|---|---|
| `daily_fetch` | 每日 05:30 | 名单刷新 + 日线增量 + 除权检测 |
| `weekly_export` | 每周一 06:10 | 导出上周三市场日线 → `exports/` → GitHub Release（`data-YYYY-Www`） |

Tushare 三模块**不进定时调度**，由 `/api/sync/run`（/sync 页一键回填）按需触发（后台子进程，全局单跑）。

### 4.4 同步水位（`sync_status` + `sync_registry.py` + `sync_freshness.py`）

- `sync_status(table_name PK, latest_date, row_count, last_synced_at)`：各表水位，避免每次扫业务表
- `sync_registry.py`：44 表注册（key/中文名/分组/日期列/module/only）+ `JOB_TABLES`（job→影响表）
- 新鲜度判定：日列 `latest < 今天` 即落后；季报类覆盖到最近已结束季度末即新鲜；逐只类永不整段跳过（内部按 symbol 跳过）
- `refresh_sync_status.py`：首次部署/水位不准时重扫重建；`audit_sync_status.py`：只读审计报表

---

## 5. API 设计（`api/`）

- FastAPI，13 个领域 router（`api/main.py` 约46行纯装配）
- 无鉴权（内网自用）；每请求短连接（`psycopg.connect`）
- `web/dist` 存在则同端口托管前端（SPA fallback）
- 主要路由组：`quotes`（行情）/ `company` / `financials` / `holders` / `market` /
  `tech` / `tushare`（增量6表）/ `tushare_full`（全量27表，26端点）/
  `screener`（选股）/ `valuation`（估值分位）/ `watchlist` / `sync`（数据更新管理）/ `health`
- 选股器：`GET /api/screener/fields` 取字段元数据 → `POST /api/screener/run`（SQL 先筛 + Python 形态过滤）

---

## 6. 前端设计（`web/`，Vue 3 + Vite + Arco Design + ECharts）

| 路由 | 页面 | 功能 |
|---|---|---|
| `/` | HomeView | 市场概览（涨跌家数/成交额/涨跌幅榜） |
| `/search` | SearchView | 股票搜索 |
| `/chart/:market/:symbol` | ChartView | K线 + MACD |
| `/company/:symbol` | CompanyView | 公司详情，20+ 懒加载 tab（财务/股东/资金/事件全量） |
| `/weeks` | WeeksView | 周数据包下载 |
| `/extra` | MarketExtraView | 市场深度（指数/龙虎榜/港通资金/两融/IPO） |
| `/sync` | SyncView | 44 表数据量/新鲜度/一键回填/任务日志 |
| `/screener` | ScreenerView | 策略选股 |
| `/watchlist` | WatchlistView | 自选股分组管理 |

CompanyView 的 tab 全部懒加载（`loadExtra(key)` 点开才请求），避免一次拉全量。

---

## 7. 发布分发设计

```
 weekly_export（自动）            export_tushare.py（手动）
 daily_bars 上周数据               41 张 Tushare 表（按保留策略裁剪）
       │                                    │
       ▼                                    ▼
 tag=data-YYYY-Www                 tag=tushare-YYYY-MM-DD
 {cn,hk,us}-{week}.parquet         {table}.parquet × 41 + manifest.json + schema.sql
       │                                    │
       └───────── GitHub Releases ──────────┘
                          │
              merger.py --repo owner/repo --db <连接串> [--fundamentals]
                          │
              ┌───────────┴───────────┐
        行情周包                 基本面包
        ingested_weeks          ingested_fundamentals
        COPY直写/daily_bars      schema.sql建表→逐表TEMP+COPY+ON CONFLICT
```

- 公开仓库附件下载无需鉴权；`manifest.json` 记录行数/日期范围/文件大小
- 全程幂等：重跑自动跳过已入库（`ingested_weeks` / `ingested_fundamentals`）

---

## 8. 配置清单

| 环境变量 | 默认 | 用途 |
|---|---|---|
| `DATABASE_URL` | 必填 | PostgreSQL 连接串 |
| `TUSHARE_TOKEN` | — | Tushare token（中转站填平台 API Key） |
| `TUSHARE_BASE_URL` | —（直连官方） | 中转站地址，如 `https://teajoin.com` |
| `TUSHARE_MIN_INTERVAL` | `0.2` | 调用间隔秒（450次/分） |
| `TUSHARE_WORKERS` | `6` | Tushare 并发线程 |
| `FETCH_WORKERS` | `8` | 行情每市场线程数 |
| `GITHUB_TOKEN` / `GITHUB_REPO` | — | weekly_export 发布用（未配则只本地导出） |
| `TZ` | `Asia/Shanghai` | 调度时区 |

---

## 9. 已知限制

1. 沙箱出口 IP 的 POST 被 teajoin WAF 拦截 → Tushare 回填必须在本地跑
2. `stk_mins` / `etf_mins` 需额外分钟权限，未覆盖；`cyq_chips` 已停更未收录
3. 东财公司信息接口在沙箱被硬封锁（502/反爬），`cn_fundamentals.py` 实质停用
4. 退市股只拉「现役名单」，历史退市覆盖不保证绝对完整
5. DaoShare/teajoin API Key 有有效期（如 2026-10-05），到期前需完成回填或续期
