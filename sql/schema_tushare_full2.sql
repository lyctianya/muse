-- Tushare 5000档全量接口（第二批）：限售解禁 + 大宗交易
-- 用法：psql "$env:DATABASE_URL" -f sql/schema_tushare_full2.sql

CREATE TABLE IF NOT EXISTS share_float (
    market TEXT NOT NULL, symbol TEXT NOT NULL,
    ann_date DATE, float_date DATE NOT NULL,
    float_share DOUBLE PRECISION, float_ratio DOUBLE PRECISION,
    holder_name TEXT, share_type TEXT,
    PRIMARY KEY (market, symbol, float_date, holder_name)
);
CREATE TABLE IF NOT EXISTS block_trade (
    market TEXT NOT NULL, symbol TEXT NOT NULL,
    trade_date DATE NOT NULL, price DOUBLE PRECISION,
    vol DOUBLE PRECISION, amount DOUBLE PRECISION,
    buyer TEXT, seller TEXT,
    PRIMARY KEY (market, symbol, trade_date, price, vol)
);
CREATE INDEX IF NOT EXISTS idx_share_float_date ON share_float (market, float_date);
CREATE INDEX IF NOT EXISTS idx_block_trade_date ON block_trade (market, trade_date);
