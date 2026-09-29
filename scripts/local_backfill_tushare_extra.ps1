# Tushare 增量数据一键回填（本地 PowerShell）
# 先决条件：.env 配好 DATABASE_URL；$env:TUSHARE_TOKEN 已设置
param(
  [string]$Only = "all",     # all|daily_basic|moneyflow|dividend|forecast
  [string]$FromDate = ""     # 断点续跑，如 "2020-01-01"
)

$ErrorActionPreference = "Stop"
$env:PGCLIENTENCODING = "UTF8"
function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Step "1/4 拉取最新代码"
git pull

Step "2/4 安装/更新依赖"
.\.venv\Scripts\pip install -q -r fetcher/requirements.txt

Step "3/4 建增量表"
psql "$env:DATABASE_URL" -f sql/schema_tushare_extra.sql

Step "4/4 回填增量数据"
$args = @("-m", "fetcher.jobs.backfill_tushare_extra", "--only", $Only)
if ($FromDate -ne "") { $args += @("--from-date", $FromDate) }
.\.venv\Scripts\python @args

Write-Host "`n完成！" -ForegroundColor Green
