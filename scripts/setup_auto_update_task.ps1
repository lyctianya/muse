# 一键创建每日自动更新的 Windows 任务计划（只需运行一次）
#
# 用法：右键 PowerShell「以管理员身份运行」，然后执行：
#   powershell -ExecutionPolicy Bypass -File scripts\setup_auto_update_task.ps1
$ErrorActionPreference = "Stop"

$TaskName = "StockDataDailyUpdate"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ScriptPath = Join-Path $ProjectRoot "scripts\daily_auto_update.ps1"

# 1. 管理员权限检查
$isAdmin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Error "需要管理员权限：请右键 PowerShell 选择「以管理员身份运行」后再执行本脚本。"
  exit 1
}

if (-not (Test-Path $ScriptPath)) {
  Write-Error "找不到 $ScriptPath"
  exit 1
}

# 2. 已存在同名任务先删除
schtasks /query /tn $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  Write-Host "已存在任务 $TaskName，先删除..."
  schtasks /delete /tn $TaskName /f | Out-Null
}

# 3. 创建任务：每天 16:30（A股收盘后）运行
$action = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File `"$ScriptPath`""
schtasks /create /tn $TaskName /tr $action /sc daily /st 16:30 /f
if ($LASTEXITCODE -ne 0) {
  Write-Error "创建任务计划失败"
  exit 1
}

# 4. 确认并打印下次运行时间
Write-Host ""
Write-Host "任务已创建，详情如下："
schtasks /query /tn $TaskName /v /fo list |
  Select-String "任务名|TaskName|下次运行时间|Next Run Time|状态|Status|触发器|Schedule Type"
Write-Host ""
Write-Host "禁用任务：schtasks /delete /tn $TaskName /f"
