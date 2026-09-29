-- 各数据表同步水位（增量起点与前端「数据更新」页以此为准）
-- 执行：psql "$DATABASE_URL" -f sql/schema_sync_status.sql
-- 初次建表后建议跑一次：python -m fetcher.jobs.refresh_sync_status

CREATE TABLE IF NOT EXISTS sync_status (
    table_name     TEXT PRIMARY KEY,              -- 与业务表名一致，如 daily_basic
    latest_date    DATE,                          -- 业务最新日期（无日期列则为 NULL）
    row_count      BIGINT NOT NULL DEFAULT 0,     -- 最近一次扫描/同步时的行数
    last_synced_at TIMESTAMPTZ,                   -- 上次成功同步或扫描时间
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE sync_status IS '各数据表同步水位；增量回填与前端状态检查优先读此表，避免反复扫业务表';
