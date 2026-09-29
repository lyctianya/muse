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
  [string]$Symbols = "",    # 指定股票，如 "600519,000001"
  [string]$Source = "tushare"  # tushare（需 TUSHARE_TOKEN）或 eastmoney
)

$ErrorActionPreference = "Stop"
$env:PGCLIENTENCODING = "UTF8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try { chcp 65001 | Out-Null } catch {}

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
Step "回填基本面（近2年，数据源=$Source）"
$pyArgs = @("-m", "fetcher.jobs.backfill_fundamentals", "--source", $Source)
if ($Limit -gt 0) { $pyArgs += @("--limit", $Limit) }
if ($Symbols -ne "") { $pyArgs += @("--symbols", $Symbols) }
.\.venv\Scripts\python @pyArgs

Step "完成"
Write-Host "基本面数据已写入本机数据库，可直接在前端查看（公司详情页 / 行业分布）。" -ForegroundColor Green