-- Tushare 15000积分档补全：第三批表（2026-09-28）
-- 覆盖：复权因子 / 股东增减持 / 日线行情 / 回购 / 质押明细 /
--       指数基本信息 / 指数权重 / 指数成分 / 筹码分布 / 沪深港股通持股
-- holder_trade 从东方财富口径迁移到 Tushare stk_holdertrade 口径
-- （东财源已永久不可用，旧数据将被完整 Tushare 数据替代）

-- ---------------------------------------------------------------- 复权因子
CREATE TABLE IF NOT EXISTS adj_factor (
    market     TEXT NOT NULL,   -- 'cn'
    symbol     TEXT NOT NULL,   -- 6位代码
    trade_date DATE NOT NULL,
    adj_factor DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_adj_factor_symbol ON adj_factor (market, symbol, trade_date DESC);

-- ------------------------------------------------------- 股东增减持（迁移）
DROP TABLE IF EXISTS holder_trade;
CREATE TABLE holder_trade (
    market       TEXT NOT NULL,   -- 'cn'
    symbol       TEXT NOT NULL,
    ann_date     DATE NOT NULL,   -- 公告日期
    holder_name  TEXT NOT NULL,   -- 股东名称
    holder_type  TEXT,            -- 股东类型 G高管/P个人/C公司
    in_de        TEXT,            -- IN增持/DE减持
    change_vol   DOUBLE PRECISION,-- 变动数量（股）
    change_ratio DOUBLE PRECISION,-- 变动比例 %
    after_share  DOUBLE PRECISION,-- 变动后持股数
    after_ratio  DOUBLE PRECISION,-- 变动后持股比例 %
    avg_price    DOUBLE PRECISION,-- 平均价格
    begin_date   DATE,            -- 变动开始日期
    close_date   DATE,            -- 变动截止日期
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, ann_date, holder_name, change_vol, begin_date)
);
CREATE INDEX IF NOT EXISTS idx_holder_trade_symbol ON holder_trade (market, symbol, ann_date DESC);

-- ------------------------------------------------------- A股日线行情（Tushare）
CREATE TABLE IF NOT EXISTS daily_ts (
    market     TEXT NOT NULL,   -- 'cn'
    symbol     TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open       DOUBLE PRECISION,
    high       DOUBLE PRECISION,
    low        DOUBLE PRECISION,
    close      DOUBLE PRECISION,
    pre_close  DOUBLE PRECISION,
    change     DOUBLE PRECISION,
    pct_chg    DOUBLE PRECISION,
    vol        DOUBLE PRECISION,  -- 成交量（手）
    amount     DOUBLE PRECISION,  -- 成交额（千元）
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_ts_symbol ON daily_ts (market, symbol, trade_date DESC);

-- ---------------------------------------------------------------- 股票回购
CREATE TABLE IF NOT EXISTS repurchase (
    market     TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    ann_date   DATE NOT NULL,   -- 公告日期
    end_date   DATE,            -- 截止日期
    proc       TEXT,            -- 进度（董事会预案/股东大会通过/实施中/完成）
    exp_date   DATE,            -- 预计完成日期
    vol        DOUBLE PRECISION,-- 回购数量（股）
    amount     DOUBLE PRECISION,-- 回购金额（元）
    price_low  DOUBLE PRECISION,-- 回购价格下限
    price_high DOUBLE PRECISION,-- 回购价格上限
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, ann_date)
);
CREATE INDEX IF NOT EXISTS idx_repurchase_symbol ON repurchase (market, symbol, ann_date DESC);

-- ------------------------------------------------------------- 股权质押明细
CREATE TABLE IF NOT EXISTS pledge_detail (
    market        TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    ann_date      DATE NOT NULL,
    holder_name   TEXT NOT NULL,   -- 出质人
    pledge_amount DOUBLE PRECISION,-- 质押数量（万股）
    start_date    DATE,            -- 质押开始日期
    end_date      DATE,            -- 质押结束日期
    is_release   TEXT,             -- 是否已解押
    release_date DATE,            -- 解押日期
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, ann_date, holder_name, start_date)
);
CREATE INDEX IF NOT EXISTS idx_pledge_detail_symbol ON pledge_detail (market, symbol, ann_date DESC);

-- ------------------------------------------------------------- 指数基本信息
CREATE TABLE IF NOT EXISTS index_basic (
    ts_code    TEXT PRIMARY KEY,  -- 指数代码
    name       TEXT,
    market     TEXT,
    publisher  TEXT,              -- 发布方
    index_type TEXT,              -- 综合/规模/行业/风格/主题/策略
    category   TEXT,              -- 指数类别
    base_date  DATE,              -- 基期
    base_point DOUBLE PRECISION,  -- 基点
    list_date  DATE,              -- 发布日期
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- 指数权重
CREATE TABLE IF NOT EXISTS index_weight (
    index_code TEXT NOT NULL,
    con_code   TEXT NOT NULL,   -- 成分代码
    trade_date DATE NOT NULL,
    weight     DOUBLE PRECISION,-- 权重 %
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (index_code, con_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_index_weight_date ON index_weight (index_code, trade_date DESC);

-- ---------------------------------------------------------------- 指数成分
CREATE TABLE IF NOT EXISTS index_member (
    index_code TEXT NOT NULL,
    con_code   TEXT NOT NULL,
    con_name   TEXT,
    in_date    DATE,              -- 纳入日期
    out_date   DATE,              -- 剔除日期
    is_new     TEXT,              -- 是否最新 Y/N
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (index_code, con_code)
);

-- ------------------------------------------------------------- 每日筹码分布
CREATE TABLE IF NOT EXISTS cyq_perf (
    market      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    trade_date  DATE NOT NULL,
    his_low     DOUBLE PRECISION,-- 历史最低价
    his_high    DOUBLE PRECISION,-- 历史最高价
    cost_5pct   DOUBLE PRECISION,-- 5%成本
    cost_15pct  DOUBLE PRECISION,-- 15%成本
    cost_50pct  DOUBLE PRECISION,-- 50%成本
    cost_85pct  DOUBLE PRECISION,-- 85%成本
    cost_95pct  DOUBLE PRECISION,-- 95%成本
    weight_avg  DOUBLE PRECISION,-- 加权平均成本
    winner_rate DOUBLE PRECISION,-- 获利盘比例 %
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_cyq_perf_symbol ON cyq_perf (market, symbol, trade_date DESC);

-- ------------------------------------------------------- 沪深港股通持股明细
CREATE TABLE IF NOT EXISTS hk_hold (
    market     TEXT NOT NULL,   -- 'cn'
    symbol     TEXT NOT NULL,
    trade_date DATE NOT NULL,
    vol        DOUBLE PRECISION,-- 持股数量（股）
    ratio      DOUBLE PRECISION,-- 持股占比 %
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_hk_hold_symbol ON hk_hold (market, symbol, trade_date DESC);
