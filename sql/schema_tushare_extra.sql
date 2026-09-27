-- Tushare Pro 5000积分档增量表（A股）
-- 行情类 daily/daily_basic 取近10年；其余取近2年
-- 在 sql/schema.sql / schema_fundamentals.sql 之后执行

-- 每日指标（PE/PB/PS/股息率/市值/换手率），近10年
CREATE TABLE IF NOT EXISTS daily_basic (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  pe            DOUBLE PRECISION,
  pe_ttm        DOUBLE PRECISION,
  pb            DOUBLE PRECISION,
  ps            DOUBLE PRECISION,
  ps_ttm        DOUBLE PRECISION,
  dv_ratio      DOUBLE PRECISION,
  dv_ttm        DOUBLE PRECISION,
  turnover_rate DOUBLE PRECISION,
  volume_ratio  DOUBLE PRECISION,
  total_mv      DOUBLE PRECISION,   -- 总市值（元）
  circ_mv       DOUBLE PRECISION,   -- 流通市值（元）
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_basic_date ON daily_basic (market, trade_date);

-- 分红送股，近2年
CREATE TABLE IF NOT EXISTS dividend (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  ann_date      DATE NOT NULL,       -- 公告日
  end_date      DATE NOT NULL,       -- 分红年度期末
  div_proc      TEXT,                -- 实施进度
  stk_div       DOUBLE PRECISION,    -- 每股送股
  stk_bo_rate   DOUBLE PRECISION,    -- 每股转增
  stk_co_rate   DOUBLE PRECISION,
  cash_div      DOUBLE PRECISION,    -- 每股分红（含税）
  cash_div_tax  DOUBLE PRECISION,    -- 每股分红（扣税后）
  record_date   DATE,                -- 股权登记日
  ex_date       DATE,                -- 除权除息日
  pay_date      DATE,                -- 派息日
  data          JSONB,
  PRIMARY KEY (market, symbol, ann_date, end_date)
);

-- 业绩预告，近2年
CREATE TABLE IF NOT EXISTS forecast (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  ann_date      DATE NOT NULL,
  end_date      DATE NOT NULL,       -- 报告期
  ptype         TEXT,               -- 预告类型
  net_profit_min DOUBLE PRECISION,  -- 净利润下限（万元）
  net_profit_max DOUBLE PRECISION,  -- 净利润上限（万元）
  last_parent_net DOUBLE PRECISION, -- 上年同期净利润
  data          JSONB,
  PRIMARY KEY (market, symbol, ann_date, end_date)
);

-- 业绩快报，近2年
CREATE TABLE IF NOT EXISTS express (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  ann_date      DATE,
  end_date      DATE NOT NULL,       -- 报告期
  revenue       DOUBLE PRECISION,    -- 营业收入（元）
  net_profit    DOUBLE PRECISION,    -- 净利润（元）
  data          JSONB,
  PRIMARY KEY (market, symbol, end_date)
);

-- 个股资金流向，近2年
CREATE TABLE IF NOT EXISTS moneyflow (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  buy_sm_amount DOUBLE PRECISION,   -- 小单买入（万元）
  sell_sm_amount DOUBLE PRECISION,
  buy_md_amount DOUBLE PRECISION,   -- 中单
  sell_md_amount DOUBLE PRECISION,
  buy_lg_amount DOUBLE PRECISION,   -- 大单
  sell_lg_amount DOUBLE PRECISION,
  buy_elg_amount DOUBLE PRECISION,  -- 特大单
  sell_elg_amount DOUBLE PRECISION,
  net_mf_amount DOUBLE PRECISION,   -- 净流入（万元）
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_moneyflow_date ON moneyflow (market, trade_date);

-- 停复牌，近2年
CREATE TABLE IF NOT EXISTS suspend (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  suspend_date  DATE NOT NULL,
  resume_date   DATE,
  ann_date      DATE,
  suspend_reason TEXT,
  PRIMARY KEY (market, symbol, suspend_date)
);
