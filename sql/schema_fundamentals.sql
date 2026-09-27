-- 股票数据管道：基本面表结构（PostgreSQL 18）
-- 第一期仅 A股（market='cn'）；港股/美股后续扩展
-- 执行：psql "$DATABASE_URL" -f sql/schema_fundamentals.sql
--
-- 设计约定：
--   * 每张表保留关键字段为列，其余原始字段存 data JSONB（接口字段有变化时不丢数据）
--   * 金额单位：元；市值单位：元；report_date 为报告期（如 2026-09-30）

-- 1. 上市公司基本信息（东方财富 stock_individual_info_em）
CREATE TABLE IF NOT EXISTS company_info (
    market          TEXT NOT NULL,   -- 'cn'
    symbol          TEXT NOT NULL,   -- '600519'
    name            TEXT,            -- 公司简称
    industry        TEXT,            -- 所属行业/板块
    pe              DOUBLE PRECISION,-- 市盈率（动）
    pb              DOUBLE PRECISION,-- 市净率
    market_cap      DOUBLE PRECISION,-- 总市值（元）
    circulating_cap DOUBLE PRECISION,-- 流通市值（元）
    total_shares    DOUBLE PRECISION,-- 总股本（股）
    circulating_shares DOUBLE PRECISION, -- 流通股本（股）
    list_date       DATE,            -- 上市日期
    data            JSONB,           -- 原始全量字段
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol)
);
COMMENT ON TABLE company_info IS '上市公司基本信息（A股）：行业/PE/PB/市值';

-- 2. 利润表（东方财富 stock_profit_sheet_by_report_em，按报告期）
CREATE TABLE IF NOT EXISTS fin_income (
    market      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    report_date DATE NOT NULL,       -- 报告期
    revenue     DOUBLE PRECISION,   -- 营业收入
    net_profit  DOUBLE PRECISION,   -- 净利润
    data        JSONB,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, report_date)
);
COMMENT ON TABLE fin_income IS '利润表（A股，按报告期）';

-- 3. 资产负债表（东方财富 stock_balance_sheet_by_report_em）
CREATE TABLE IF NOT EXISTS fin_balance (
    market       TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    report_date  DATE NOT NULL,
    total_assets DOUBLE PRECISION,  -- 资产总计
    total_liab   DOUBLE PRECISION,  -- 负债合计
    equity       DOUBLE PRECISION,  -- 股东权益合计
    data         JSONB,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, report_date)
);
COMMENT ON TABLE fin_balance IS '资产负债表（A股，按报告期）';

-- 4. 现金流量表（东方财富 stock_cash_flow_sheet_by_report_em）
CREATE TABLE IF NOT EXISTS fin_cashflow (
    market      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    report_date DATE NOT NULL,
    data        JSONB,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, report_date)
);
COMMENT ON TABLE fin_cashflow IS '现金流量表（A股，按报告期）';

-- 5. 财务指标（同花顺 stock_financial_analysis_indicator）
CREATE TABLE IF NOT EXISTS fin_indicator (
    market       TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    report_date  DATE NOT NULL,
    roe          DOUBLE PRECISION,   -- 净资产收益率
    gross_margin DOUBLE PRECISION,   -- 毛利率
    net_margin   DOUBLE PRECISION,   -- 净利率
    data         JSONB,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, report_date)
);
COMMENT ON TABLE fin_indicator IS '财务指标（A股，按报告期）：ROE/毛利率/净利率等';

-- 6. 主营业务构成（东方财富 stock_zygc_em）
CREATE TABLE IF NOT EXISTS main_business (
    market       TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    report_date  DATE NOT NULL,      -- 报告期
    category     TEXT NOT NULL,      -- '按产品' | '按地区'
    item         TEXT NOT NULL,      -- 产品/地区名称
    revenue      DOUBLE PRECISION,   -- 营业收入
    revenue_ratio DOUBLE PRECISION, -- 收入占比
    profit       DOUBLE PRECISION,   -- 营业利润
    profit_ratio DOUBLE PRECISION,   -- 利润占比
    PRIMARY KEY (market, symbol, report_date, category, item)
);
COMMENT ON TABLE main_business IS '主营业务构成（A股，按报告期/分类）';

-- 7. 前十大股东 / 前十大流通股东（东方财富 stock_gdfx_top_10_em / stock_gdfx_free_top_10_em）
CREATE TABLE IF NOT EXISTS top_holders (
    market      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    report_date DATE NOT NULL,       -- 报告期（季度）
    holder_type TEXT NOT NULL,       -- 'top10' | 'float10'
    rank        INTEGER NOT NULL,    -- 1..10
    holder_name TEXT,                -- 股东名称
    hold_shares DOUBLE PRECISION,   -- 持股数量（股）
    hold_ratio  DOUBLE PRECISION,   -- 持股比例 %
    change      DOUBLE PRECISION,   -- 增减（股）
    PRIMARY KEY (market, symbol, report_date, holder_type, rank)
);
COMMENT ON TABLE top_holders IS '前十大股东 / 前十大流通股东（A股，按季度）';

-- 8. 股权质押（东方财富 stock_gpzy_pledge_ratio_em）
CREATE TABLE IF NOT EXISTS pledge_info (
    market        TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    stat_date     DATE NOT NULL,     -- 统计日期
    pledge_ratio  DOUBLE PRECISION, -- 质押比例 %
    pledged_shares DOUBLE PRECISION,-- 质押股数
    data          JSONB,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, stat_date)
);
COMMENT ON TABLE pledge_info IS '股权质押（A股）';

-- 9. 股东人数（东方财富 stock_zh_a_gdhs_detail_em）
CREATE TABLE IF NOT EXISTS holder_number (
    market       TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    report_date  DATE NOT NULL,      -- 统计日期
    holder_count BIGINT,             -- 股东人数（户）
    avg_shares   DOUBLE PRECISION,   -- 户均持股
    data         JSONB,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, report_date)
);
COMMENT ON TABLE holder_number IS '股东人数（A股，历史序列）';

-- 10. 股东增减持（东方财富 stock_ggcg_em，symbol=股东增持/股东减持）
CREATE TABLE IF NOT EXISTS holder_trade (
    id          BIGSERIAL PRIMARY KEY,
    market      TEXT NOT NULL,       -- 'cn'
    symbol      TEXT NOT NULL,       -- 股票代码
    holder_name TEXT,                -- 股东名称
    trade_type  TEXT NOT NULL,       -- '增持' | '减持'
    trade_date  DATE,                -- 变动日期
    shares      DOUBLE PRECISION,   -- 变动股数
    price       DOUBLE PRECISION,   -- 成交均价
    amount      DOUBLE PRECISION,   -- 变动金额
    ratio       DOUBLE PRECISION,   -- 变动比例 %
    data        JSONB,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (market, symbol, holder_name, trade_type, trade_date, shares)
);
COMMENT ON TABLE holder_trade IS '股东增减持（A股）';
CREATE INDEX IF NOT EXISTS idx_holder_trade_symbol ON holder_trade (market, symbol, trade_date DESC);
