<#Requires -Version 5.1
<#
.SYNOPSIS
  A股基本面一键回填（本机运行）：建表 -> 回填近2年数据 -> 入库完成。

.DESCRIPTION
  沙箱网络连不上东方财富，所以基本面抓取只能在本机跑。
  数据直接写入本机 PostgreSQL，不需要导出/下载/合并。

.用法：
  powershell -ExecutionPolicy Bypass -File scripts\local_backfill_fundamentals.ps1
  powershell -ExecutionPolicy Bypass -File scripts\local_backfill_fundamentals.ps1 -Limit 5
#>
param(
  [int]$Limit = 0,          # 先验证用 -Limit 5；0 = 全量
  [string]$Symbols = ""     # 指定股票，如 "600519,000001"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $root

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# 1. 拉最新代码
Step "git pull"
git pull

# 2. 建表
Step "创建基本面表结构"
if (-not $env:DATABASE_URL) { throw "请先设置 `$env:DATABASE_URL" }
psql "$env:DATABASE_URL" -f sql/schema_fundamentals.sql

# 3. 装依赖
Step "安装依赖"
.\.venv\Scripts\python -m pip install -q -r fetcher/requirements.txt

# 4. 回填
Step "回填基本面（近2年）"
$args = @("-m", "fetcher.jobs.backfill_fundamentals")
if ($Limit -gt 0) { $args += @("--limit", $Limit) }
if ($Symbols -ne "") { $args += @("--symbols", $Symbols) }
.\.venv\Scripts\python @args

Step "完成"
Write-Host "基本面数据已写入本机数据库，可直接在前端查看（公司详情页 / 行业分布）。" -ForegroundColor Green
