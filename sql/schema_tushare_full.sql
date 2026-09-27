-- Tushare Pro 5000积分档全量接口增量表（A股）
-- 在 schema.sql / schema_fundamentals.sql / schema_tushare_extra.sql 之后执行

-- 主营业务构成（Tushare 官方，替代东方财富爬虫）
CREATE TABLE IF NOT EXISTS fina_mainbz (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  end_date      DATE NOT NULL,
  bz_item       TEXT,                -- 主营项目名称
  bz_sales      DOUBLE PRECISION,    -- 主营业务收入（元）
  bz_profit     DOUBLE PRECISION,    -- 主营业务利润（元）
  bz_cost       DOUBLE PRECISION,    -- 主营业务成本（元）
  curr_type     TEXT,               -- 货币代码
  update_flag   TEXT,
  PRIMARY KEY (market, symbol, end_date, bz_item)
);

-- 上市公司详细信息
CREATE TABLE IF NOT EXISTS company_detail (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  exchange      TEXT,
  chairman      TEXT,                -- 法人代表
  manager       TEXT,                -- 总经理
  secretary     TEXT,                -- 董秘
  reg_capital   DOUBLE PRECISION,    -- 注册资本（万元）
  setup_date    DATE,                -- 注册日期
  province      TEXT,
  city          TEXT,
  introduction  TEXT,                -- 公司介绍
  website       TEXT,
  email         TEXT,
  office        TEXT,                -- 办公地址
  employees     INTEGER,             -- 员工人数
  main_business TEXT,                -- 主要业务
  business_scope TEXT,               -- 经营范围
  PRIMARY KEY (market, symbol)
);

-- 股票曾用名
CREATE TABLE IF NOT EXISTS namechange (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  start_date    DATE NOT NULL,
  end_date      DATE,
  old_name      TEXT,
  PRIMARY KEY (market, symbol, start_date)
);

-- 龙虎榜每日明细
CREATE TABLE IF NOT EXISTS top_list (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  name          TEXT,
  close         DOUBLE PRECISION,
  pct_change    DOUBLE PRECISION,
  turnover_rate DOUBLE PRECISION,
  amount        DOUBLE PRECISION,    -- 总成交额（万元）
  l_sell        DOUBLE PRECISION,    -- 龙虎榜卖出额（万元）
  l_buy         DOUBLE PRECISION,    -- 龙虎榜买入额（万元）
  l_amount      DOUBLE PRECISION,    -- 龙虎榜成交额（万元）
  net_amount    DOUBLE PRECISION,    -- 净买入额（万元）
  net_rate      DOUBLE PRECISION,    -- 净买额占总成交比
  amount_rate   DOUBLE PRECISION,    -- 成交额占总成交比
  float_values  DOUBLE PRECISION,    -- 流通市值（万元）
  reason        TEXT,                -- 上榜原因
  PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_top_list_date ON top_list (market, trade_date);

-- 龙虎榜机构明细
CREATE TABLE IF NOT EXISTS top_inst (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  side          INTEGER,             -- 0 买方 1 卖方
  exalter       TEXT,                -- 营业部名称
  buy           DOUBLE PRECISION,    -- 买入额（万元）
  buy_rate      DOUBLE PRECISION,
  sell          DOUBLE PRECISION,    -- 卖出额（万元）
  sell_rate     DOUBLE PRECISION,
  net_buy       DOUBLE PRECISION,    -- 净买入（万元）
  PRIMARY KEY (market, symbol, trade_date, side, exalter)
);

-- 指数日线（000001.SH 上证综指等）
CREATE TABLE IF NOT EXISTS index_daily (
  market        TEXT NOT NULL,        -- cn
  ts_code       TEXT NOT NULL,        -- 000001.SH
  trade_date    DATE NOT NULL,
  open          DOUBLE PRECISION,
  high          DOUBLE PRECISION,
  low           DOUBLE PRECISION,
  close         DOUBLE PRECISION,
  pre_close     DOUBLE PRECISION,
  change        DOUBLE PRECISION,
  pct_change    DOUBLE PRECISION,
  vol           DOUBLE PRECISION,     -- 成交量（手）
  amount        DOUBLE PRECISION,     -- 成交额（千元）
  PRIMARY KEY (market, ts_code, trade_date)
);

-- 沪深港通资金流向（市场级）
CREATE TABLE IF NOT EXISTS moneyflow_hsgt (
  market        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  ggt_ss        DOUBLE PRECISION,     -- 港股通上海净买入（万元）
  ggt_sz        DOUBLE PRECISION,     -- 港股通深圳净买入（万元）
  hgt           DOUBLE PRECISION,     -- 沪股通净买入（万元）
  sgt           DOUBLE PRECISION,     -- 深股通净买入（万元）
  north_money   DOUBLE PRECISION,     -- 北向净买入（万元）
  south_money   DOUBLE PRECISION,     -- 南向净买入（万元）
  PRIMARY KEY (market, trade_date)
);

-- 沪深股通十大成交股
CREATE TABLE IF NOT EXISTS hsgt_top10 (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  gtype         TEXT,                -- 类型：沪/深
  rank          INTEGER,
  buy_amount    DOUBLE PRECISION,    -- 买入金额（万元）
  sell_amount   DOUBLE PRECISION,    -- 卖出金额（万元）
  net_amount    DOUBLE PRECISION,    -- 净买入（万元）
  PRIMARY KEY (market, symbol, trade_date, gtype)
);

-- 财报披露计划
CREATE TABLE IF NOT EXISTS disclosure_date (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  end_date      DATE NOT NULL,        -- 报告期
  ann_date      DATE,                -- 预计披露日
  pre_date      DATE,                -- 预披露日期
  actual_date   DATE,                -- 实际披露日
  PRIMARY KEY (market, symbol, end_date)
);

-- 融资融券交易汇总（市场级）
CREATE TABLE IF NOT EXISTS margin (
  market        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  exchange_id   TEXT,                -- SSE/SZSE
  rzye          DOUBLE PRECISION,    -- 融资余额（元）
  rqye          DOUBLE PRECISION,    -- 融券余额（元）
  rzrqye        DOUBLE PRECISION,    -- 融资融券余额（元）
  rqyl          DOUBLE PRECISION,    -- 融券余量（股）
  rzrqye_rate   DOUBLE PRECISION,
  PRIMARY KEY (market, trade_date, exchange_id)
);

-- 个股两融明细
CREATE TABLE IF NOT EXISTS margin_detail (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  rzye          DOUBLE PRECISION,     -- 融资余额（元）
  rqye          DOUBLE PRECISION,     -- 融券余额（元）
  rzrqye        DOUBLE PRECISION,     -- 两融余额（元）
  rqyl          DOUBLE PRECISION,     -- 融券余量（股）
  rzye_rate     DOUBLE PRECISION,
  PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_margin_detail_date ON margin_detail (market, trade_date);

-- 每日涨跌停价格
CREATE TABLE IF NOT EXISTS stk_limit (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  pre_close     DOUBLE PRECISION,
  up_limit      DOUBLE PRECISION,     -- 涨停价
  down_limit    DOUBLE PRECISION,     -- 跌停价
  PRIMARY KEY (market, symbol, trade_date)
);

-- 财务审计意见
CREATE TABLE IF NOT EXISTS fina_audit (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  end_date      DATE NOT NULL,
  ann_date      DATE,
  audit_result  TEXT,                -- 审计结果
  audit_fees    DOUBLE PRECISION,     -- 审计费用（元）
  audit_agency  TEXT,                -- 会计师事务所
  data          JSONB,
  PRIMARY KEY (market, symbol, end_date)
);

-- IPO 新股列表
CREATE TABLE IF NOT EXISTS new_share (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  name          TEXT,
  price         DOUBLE PRECISION,     -- 发行价格
  total_amount  DOUBLE PRECISION,     -- 发行总数（万股）
  online_amount DOUBLE PRECISION,     -- 网上发行（万股）
  issue_date    DATE,                -- 发行日期
  list_date     DATE,                -- 上市日期
  data          JSONB,
  PRIMARY KEY (market, symbol)
);

-- 上市公司管理层
CREATE TABLE IF NOT EXISTS managers (
  market        TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  name          TEXT NOT NULL,
  gender        TEXT,
  lev           TEXT,                -- 岗位类别
  title         TEXT,                -- 职务
  edu           TEXT,                -- 学历
  national      TEXT,                -- 国籍
  birthday      TEXT,
  begin_date    DATE,                -- 上任日期
  end_date      DATE,                -- 离任日期
  resume        TEXT,                -- 简历
  ann_date      DATE,
  PRIMARY KEY (market, symbol, name, ann_date)
);
