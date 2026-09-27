-- 自选股（单用户，user_id 固定为 'default'）
CREATE TABLE IF NOT EXISTS watchlist (
    user_id TEXT NOT NULL DEFAULT 'default',
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    group_name TEXT NOT NULL DEFAULT '默认分组',
    note TEXT DEFAULT '',
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, market, symbol)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist (user_id);
