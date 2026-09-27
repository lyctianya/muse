# 每日收盘后自动更新（本地 Windows 任务计划调用）
#
# 内容：Tushare A股增量/全量接口幂等回填 + 日线行情增量拉取
# 先决条件：
#   1. 项目根 .env 配好 DATABASE_URL、TUSHARE_TOKEN
#   2. .venv 已建好（.\.venv\Scripts\python.exe 存在）
#
# 手动运行示例：
#   powershell -ExecutionPolicy Bypass -File scripts\daily_auto_update.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\daily_auto_update.ps1 -SkipGitPull
param(
  [string]$LogDir = "logs",   # 日志目录（相对路径按项目根解析）
  [switch]$SkipGitPull         # 跳过 git pull（网络不好时用）
)

$ErrorActionPreference = "Continue"   # 单个步骤失败不中断整体

$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

# 日志文件：logs/auto_update_YYYYMMDD.log
if (-not [System.IO.Path]::IsPathRooted($LogDir)) {
  $LogDir = Join-Path $ProjectRoot $LogDir
}
if (-not (Test-Path $LogDir)) {
  New-Item -ItemType Directory -Path $LogDir | Out-Null
}
$Stamp = Get-Date -Format "yyyyMMdd"
$LogFile = Join-Path $LogDir "auto_update_${Stamp}.log"

function Write-Log($msg) {
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
  $line | Tee-Object -FilePath $LogFile -Append | Out-Null
  Write-Host $line
}

function Invoke-Step($Name, [scriptblock]$Action) {
  # 子进程的全部输出流同时进控制台和日志文件（定时任务无人值守时可查）
  Write-Log ">>> 开始：$Name"
  $t0 = Get-Date
  & $Action *>&1 | Tee-Object -FilePath $LogFile -Append
  $code = $LASTEXITCODE
  if ($null -eq $code) { $code = -1 }
  $secs = [int]((Get-Date) - $t0).TotalSeconds
  if ($code -eq 0) {
    Write-Log "<<< 完成：$Name，耗时 ${secs}s，退出码 0"
  } else {
    Write-Log "<<< 失败：$Name，耗时 ${secs}s，退出码 $code（继续下一步）"
  }
}

Write-Log "========== 每日自动更新开始（SkipGitPull=$($SkipGitPull.IsPresent)） =========="

# 周末直接退出（节假日不处理）
$dow = (Get-Date).DayOfWeek
if ($dow -eq [DayOfWeek]::Saturday -or $dow -eq [DayOfWeek]::Sunday) {
  Write-Log "今天是 $dow（周末非交易日），跳过更新"
  exit 0
}

$Py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Pip = Join-Path $ProjectRoot ".venv\Scripts\pip.exe"
if (-not (Test-Path $Py)) {
  Write-Log "错误：找不到 $Py，请先建好 .venv 再运行"
  exit 1
}

# 1. 拉取最新代码
if (-not $SkipGitPull) {
  Invoke-Step "git pull" { git pull }
} else {
  Write-Log "跳过 git pull（-SkipGitPull）"
}

# 2. 安装/更新依赖
Invoke-Step "pip 安装/更新依赖" { & $Pip install -q -r (Join-Path $ProjectRoot "fetcher\requirements.txt") }

# 3. Tushare 回填（幂等 upsert，单个失败记日志继续下一个）
$jobs = @(
  @("每日指标 daily_basic",      @("-m", "fetcher.jobs.backfill_tushare_extra", "--only", "daily_basic")),
  @("资金流向+停复牌 moneyflow", @("-m", "fetcher.jobs.backfill_tushare_extra", "--only", "moneyflow")),
  @("业绩预告+快报 forecast",    @("-m", "fetcher.jobs.backfill_tushare_extra", "--only", "forecast")),
  @("龙虎榜 top_list",           @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "top_list")),
  @("两融 margin",               @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "margin")),
  @("北向资金 hsgt_flow",        @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "hsgt_flow")),
  @("陆股通十大 hsgt_top10",     @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "hsgt_top10")),
  @("涨跌停 stk_limit",          @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "stk_limit")),
  @("大宗交易 block_trade",      @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "block_trade")),
  @("披露计划 disclosure",       @("-m", "fetcher.jobs.backfill_tushare_full", "--only", "disclosure"))
)
foreach ($j in $jobs) {
  $stepName = $j[0]
  $stepArgs = $j[1]
  Invoke-Step $stepName { & $Py @stepArgs }
}

# 4. 日线行情增量（三市场现役名单刷新 + 增量拉取）
$dailyFetch = Join-Path $ProjectRoot "fetcher\jobs\daily_fetch.py"
if (Test-Path $dailyFetch) {
  Invoke-Step "日线行情增量 daily_fetch" { & $Py -m fetcher.jobs.daily_fetch }
} else {
  Write-Log "跳过：未找到 fetcher/jobs/daily_fetch.py，日线行情增量未执行"
}

Write-Log "========== 每日自动更新结束 =========="
