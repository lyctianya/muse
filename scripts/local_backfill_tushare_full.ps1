# Tushare 全量接口一键回填（本地 PowerShell，5000积分档 15 张新表）
# 先决条件：.env 配好 DATABASE_URL；$env:TUSHARE_TOKEN=你的token
# 走中转站（如 DaoShare/teajoin）时：$env:TUSHARE_TOKEN=平台API Key；$env:TUSHARE_BASE_URL="https://teajoin.com"
param(
  [string]$Only = "all",     # all|company_detail|namechange|new_share|disclosure|
                             # index|hsgt_flow|hsgt_top10|margin|top_list|
                             # stk_limit|mainbz|fina_audit|managers
  [string]$FromDate = ""     # 断点续跑，如 "2025-01-01"
)

$ErrorActionPreference = "Stop"
function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Step "1/4 拉取最新代码"
git pull

Step "2/4 安装/更新依赖"
.\.venv\Scripts\pip install -q -r fetcher/requirements.txt

Step "3/4 建全量表"
psql "$env:DATABASE_URL" -f sql/schema_tushare_full.sql

Step "4/4 回填全量数据"
$args = @("-m", "fetcher.jobs.backfill_tushare_full", "--only", $Only)
if ($FromDate -ne "") { $args += @("--from-date", $FromDate) }
.\.venv\Scripts\python @args

Write-Host "`n完成！" -ForegroundColor Green
