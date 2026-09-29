# 合并工具（merger）

把 GitHub Releases 上的周 Parquet 数据包幂等合并到本地 PostgreSQL。
独立运行，不依赖项目其他部分。

## 安装

```bash
pip install -r requirements.txt
```

## 用法

```bash
# 合并某仓库的全部周数据到本地库
python merger.py --repo owner/repo --db postgresql://user:pass@localhost:5432/stocks

# 只合并指定周
python merger.py --repo owner/repo --db postgresql://user:pass@localhost:5432/stocks --week 2026-W39

# 同时合并基本面 Release（tushare-YYYY-MM-DD，41 张 Tushare 表）
python merger.py --repo owner/repo --db postgresql://user:pass@localhost:5432/stocks --fundamentals

# 只合并指定的基本面 Release
python merger.py --repo owner/repo --db <连接串> --fund-tag tushare-2026-09-29

# --db 缺省时读取 DATABASE_URL 环境变量
export DATABASE_URL=postgresql://user:pass@localhost:5432/stocks
python merger.py --repo owner/repo
```

## 说明

- 公开仓库的 Releases 附件下载无需 GitHub 鉴权
- 本地 `ingested_weeks` 表记录已入库的周，重复运行自动跳过
- 入库先用 `COPY` 极速写入；遇主键冲突自动降级为 `ON CONFLICT DO UPDATE` 兜底
- `--fundamentals`：处理 `tushare-YYYY-MM-DD`（新）/ `fundamentals-YYYY-MM-DD`（旧）Release；
  先执行包内自带的 `schema.sql` 建表，再逐表 TEMP + COPY + `ON CONFLICT` 幂等合并，
  已合并的 tag 记在 `ingested_fundamentals` 表
- Parquet 是通用格式，不用本工具也能导入 DuckDB / SQLite 等
