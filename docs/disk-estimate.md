# 回填磁盘容量估算（2026-09-26）

## 输入
- 公式：symbols × 2500 交易日 × 230 字节/行
- 目标分区：/home/hatch（PostgreSQL 数据目录 /home/hatch/pgdata 所在盘）

## 各市场 symbol 数
| 市场 | 数量 | 来源 |
|------|------|------|
| cn 股票 | 5,569 | 实测（akshare stock_info_a_code_name，经 TLS 补丁） |
| cn ETF | ~950 | 估计（akshare fund_etf_spot_em 当前被代理 502 挡住） |
| hk | ~2,600 | 估计（stock_hk_spot_em 当前被代理挡住） |
| us（含 ETF） | 13,251 | 实测（Nasdaq nasdaqtraded.txt 官方名单，按代码过滤） |
| 合计 | ~22,370 | |

## 估算
- 数据行：22,370 × 2,500 × 230 B ≈ 12.9 GB
- 含索引（按 +40%）：约 18 GB
- 即使数量整体偏差 +50%：约 27 GB

## 分区可用空间
- /home/hatch：99G 可用（df 实测，100G 持久盘）
- 保留 1GB 余量后可用：约 98G
- 18 GB（乃至 27 GB）<< 98 GB

## 结论：空间充足，可以执行回填。
