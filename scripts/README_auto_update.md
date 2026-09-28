# 每日自动更新（定时任务）说明

## 两个脚本

| 脚本 | 作用 | 运行频率 |
|---|---|---|
| `scripts/daily_auto_update.ps1` | 实际执行数据更新：git pull → 装依赖 → Tushare 10 个回填任务 → 日线行情增量 | 每天 16:30 由任务计划自动调用，也可手动跑 |
| `scripts/setup_auto_update_task.ps1` | 一键创建 Windows 任务计划 `StockDataDailyUpdate`（每天 16:30） | 只需运行一次 |

## 首次设置（只需一次）

1. 确认项目根 `.env` 配好 `DATABASE_URL` 和 `TUSHARE_TOKEN`。
   走 Tushare 中转站（如 DaoShare/teajoin）时：`TUSHARE_TOKEN` 填平台 API Key，
   另加一行 `TUSHARE_BASE_URL=https://teajoin.com`。
2. 右键 PowerShell → **以管理员身份运行**，执行：
   ```powershell
   cd H:\GitHub\muse
   powershell -ExecutionPolicy Bypass -File scripts\setup_auto_update_task.ps1
   ```
3. 看到任务详情和下次运行时间即成功。电脑需在 16:30 处于开机状态。
   如创建时提示输入密码，填 Windows 登录密码即可。

## 日志

- 位置：`logs/auto_update_YYYYMMDD.log`（项目根下）
- 每个步骤记开始/结束/耗时/退出码；单个任务失败不中断整体，可在日志里看到是哪一步失败。

## 手动运行

```powershell
cd H:\GitHub\muse
# 完整跑一遍（含 git pull）
powershell -ExecutionPolicy Bypass -File scripts\daily_auto_update.ps1
# 跳过 git pull
powershell -ExecutionPolicy Bypass -File scripts\daily_auto_update.ps1 -SkipGitPull
```

## 禁用 / 删除任务

```powershell
schtasks /delete /tn StockDataDailyUpdate /f
```

## 注意事项

- 周六/周日自动跳过（日志会记一笔）；**法定节假日不处理**，那几天任务会空跑一遍（幂等，无数据可更新）。
- 大宗交易（`block_trade`）回填任务需等该功能代码合并后才生效，在此之前该步骤会失败并记日志，不影响其他步骤。
- 任务以当前用户身份运行，请确保该用户能访问项目目录和 PostgreSQL。
