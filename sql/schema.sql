-- 股票数据管道：数据库表结构（PostgreSQL 18）
-- 执行：psql "$DATABASE_URL" -f sql/schema.sql

-- 股票基本信息（现役名单）
CREATE TABLE IF NOT EXISTS symbols (
    market   TEXT NOT NULL,          -- 'cn' | 'hk' | 'us'
    symbol   TEXT NOT NULL,          -- '600519' | '00700' | 'AAPL'
    name     TEXT NOT NULL,          -- 股票/ETF 名称
    currency TEXT NOT NULL,          -- 'CNY' | 'HKD' | 'USD'
    active   BOOLEAN NOT NULL DEFAULT TRUE,  -- FALSE=已退市或不再活跃（软删除）
    PRIMARY KEY (market, symbol)
);
COMMENT ON TABLE symbols IS '三市场现役股票（含ETF）名单';

-- 日线行情（前复权，以最新交易日为锚点）
CREATE TABLE IF NOT EXISTS daily_bars (
    market     TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open       DOUBLE PRECISION NOT NULL,  -- 开盘（前复权）
    high       DOUBLE PRECISION NOT NULL,  -- 最高（前复权）
    low        DOUBLE PRECISION NOT NULL,   -- 最低（前复权）
    close      DOUBLE PRECISION NOT NULL,   -- 收盘（前复权）
    volume     BIGINT NOT NULL,             -- 成交量（cn=手，hk/us=股）
    amount     DOUBLE PRECISION,            -- 成交额（原币种；美股无则为 NULL）
    pct_change DOUBLE PRECISION,           -- 涨跌幅 %
    currency   TEXT NOT NULL,               -- 'CNY' | 'HKD' | 'USD'
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, trade_date)
);
COMMENT ON TABLE daily_bars IS '三市场日线行情（前复权）';

CREATE INDEX IF NOT EXISTS idx_bars_symbol_date
    ON daily_bars (market, symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_bars_date
    ON daily_bars (trade_date DESC);

-- 合并工具 bookkeeping：已入库的周（merger 幂等依据）
CREATE TABLE IF NOT EXISTS ingested_weeks (
    market TEXT NOT NULL,   -- 'cn' | 'hk' | 'us'
    week   TEXT NOT NULL,   -- '2026-W39'
    PRIMARY KEY (market, week)
);
COMMENT ON TABLE ingested_weeks IS 'merger 已合并入库的周（按市场）';
