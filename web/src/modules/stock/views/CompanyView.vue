<template>
  <a-card class="stock-head" :bordered="false">
    <template #title>
      <a-space>
        <a-button shape="circle" @click="$router.back()"><icon-left /></a-button>
        <span class="stock-title">{{ title }}</span>
        <a-tag color="arcoblue">A股</a-tag>
        <WatchStar market="cn" :symbol="props.symbol" />
      </a-space>
    </template>
    <template #extra>
      <a-range-picker
        v-model="range"
        value-format="YYYY-MM-DD"
        style="width: 280px"
        @change="loadAll"
      />
    </template>

    <a-spin :loading="loading" style="width: 100%">
      <!-- 基本信息 -->
      <a-descriptions
        v-if="company.found"
        :column="4"
        bordered
        size="small"
        style="margin-bottom: 16px"
        title="公司基本信息"
      >
        <a-descriptions-item label="公司名称">{{ company.name }}</a-descriptions-item>
        <a-descriptions-item label="所属行业">{{ company.industry || '--' }}</a-descriptions-item>
        <a-descriptions-item label="上市日期">{{ company.list_date || '--' }}</a-descriptions-item>
        <a-descriptions-item label="市盈率(动)">{{ fmtNum(company.pe) }}</a-descriptions-item>
        <a-descriptions-item label="市净率">{{ fmtNum(company.pb) }}</a-descriptions-item>
        <a-descriptions-item label="总市值">{{ fmtMoney(company.market_cap) }}</a-descriptions-item>
        <a-descriptions-item label="流通市值">{{ fmtMoney(company.circulating_cap) }}</a-descriptions-item>
        <a-descriptions-item label="总股本">{{ fmtNum(company.total_shares) }}</a-descriptions-item>
      </a-descriptions>
      <a-empty v-else description="暂无公司基本信息（需先回填基本面数据）" style="margin-bottom: 16px" />

      <!-- K线 + MACD -->
      <a-card title="K线 / MACD" size="small" style="margin-bottom: 16px">
        <div ref="chartEl" style="width: 100%; height: 520px"></div>
      </a-card>

      <!-- 财务趋势图 -->
      <a-row :gutter="16" style="margin-bottom: 16px">
        <a-col :span="12">
          <a-card title="营收 / 净利润趋势" size="small">
            <div v-if="financials.income.length" ref="incomeEl" style="width: 100%; height: 300px"></div>
            <a-empty v-else description="暂无数据" />
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card title="ROE / 毛利率 / 净利率趋势" size="small">
            <div v-if="financials.indicator.length" ref="roeEl" style="width: 100%; height: 300px"></div>
            <a-empty v-else description="暂无数据" />
          </a-card>
        </a-col>
      </a-row>

      <!-- 财务 / 股东 Tabs（lazy-load：只渲染激活过的 tab，首屏更快） -->
      <a-tabs
        v-model:active-key="activeTab"
        class="company-tabs"
        lazy-load
        @change="onTabChange"
      >
        <a-tab-pane key="income" title="利润表">
          <FinTable
            :rows="financials.income"
            :extras="[
              { key: 'revenue', title: '营收' },
              { key: 'net_profit', title: '净利润' },
            ]"
          />
        </a-tab-pane>
        <a-tab-pane key="balance" title="资产负债表">
          <FinTable
            :rows="financials.balance"
            :extras="[
              { key: 'total_assets', title: '总资产' },
              { key: 'total_liab', title: '总负债' },
            ]"
          />
        </a-tab-pane>
        <a-tab-pane key="cashflow" title="现金流量表">
          <FinTable :rows="financials.cashflow" />
        </a-tab-pane>
        <a-tab-pane key="indicator" title="财务指标">
          <FinTable
            :rows="financials.indicator"
            :extras="[
              { key: 'roe', title: 'ROE%' },
              { key: 'gross_margin', title: '毛利率%' },
              { key: 'net_margin', title: '净利率%' },
            ]"
          />
        </a-tab-pane>
        <a-tab-pane key="business" title="主营业务">
          <a-table :data="business" :pagination="{ pageSize: 20 }" size="small">
            <template #columns>
              <a-table-column title="报告期" data-index="report_date" />
              <a-table-column title="分类" data-index="category" />
              <a-table-column title="项目" data-index="item" />
              <a-table-column title="营收" data-index="revenue">
                <template #cell="{ record }">{{ fmtMoney(record.revenue) }}</template>
              </a-table-column>
              <a-table-column title="营收占比" data-index="revenue_ratio">
                <template #cell="{ record }">{{ fmtPct(record.revenue_ratio) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="holders" title="十大股东">
          <a-table :data="holders" :pagination="{ pageSize: 20 }" size="small">
            <template #columns>
              <a-table-column title="报告期" data-index="report_date" />
              <a-table-column title="排名" data-index="rank" />
              <a-table-column title="股东名称" data-index="holder_name" />
              <a-table-column title="持股数" data-index="hold_shares">
                <template #cell="{ record }">{{ fmtNum(record.hold_shares) }}</template>
              </a-table-column>
              <a-table-column title="持股比例" data-index="hold_ratio">
                <template #cell="{ record }">{{ fmtPct(record.hold_ratio) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="trades" title="股东增减持">
          <a-table :data="trades" :pagination="{ pageSize: 20 }" size="small">
            <template #columns>
              <a-table-column title="日期" data-index="trade_date" />
              <a-table-column title="股东" data-index="holder_name" />
              <a-table-column title="类型" data-index="trade_type">
                <template #cell="{ record }">
                  <a-tag :color="record.trade_type === '增持' ? 'red' : 'green'">
                    {{ record.trade_type }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column title="变动股数" data-index="shares">
                <template #cell="{ record }">{{ fmtNum(record.shares) }}</template>
              </a-table-column>
              <a-table-column title="变动比例%" data-index="ratio">
                <template #cell="{ record }">{{ fmtNum(record.ratio) }}</template>
              </a-table-column>
              <a-table-column title="均价" data-index="price">
                <template #cell="{ record }">{{ fmtNum(record.price) }}</template>
              </a-table-column>
              <a-table-column title="变动后持股" data-index="after_share">
                <template #cell="{ record }">{{ fmtNum(record.after_share) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="daily-basic" title="每日指标">
          <div v-if="valuation && valuation.found">
            <a-card title="估值历史分位" size="small" style="margin-bottom: 16px">
              <a-row :gutter="24">
                <a-col :span="12" v-for="item in valItems" :key="item.key">
                  <div style="margin-bottom: 4px">
                    <span style="font-weight: 600">{{ item.label }}</span>
                    <span style="font-size: 20px; margin-left: 8px">{{ fmtNum(item.stat.current) }}</span>
                    <span style="color: var(--color-text-3); margin-left: 8px; font-size: 12px">
                      处于近 {{ item.stat.span_years }} 年 {{ item.stat.quantile }}% 分位
                      （样本 {{ item.stat.count }} 个）
                    </span>
                  </div>
                  <div style="position: relative; height: 10px; border-radius: 5px; margin: 8px 0 4px;
                              background: linear-gradient(90deg, #00b42a, #ffb400 50%, #f53f3f)">
                    <div :style="{ position: 'absolute', left: item.stat.quantile + '%', top: '-4px',
                                   width: '3px', height: '18px', background: '#1d2129', borderRadius: '2px',
                                   transform: 'translateX(-50%)' }"></div>
                  </div>
                  <div style="display: flex; justify-content: space-between; font-size: 12px;
                              color: var(--color-text-3); margin-bottom: 12px">
                    <span>便宜 ←</span><span>→ 贵</span>
                  </div>
                  <div :ref="(el) => (item.key === 'pe' ? valPeEl = el : valPbEl = el)"
                       style="width: 100%; height: 240px"></div>
                </a-col>
              </a-row>
            </a-card>
          </div>
          <a-empty v-if="dailyBasicLoaded && !(valuation && valuation.found)"
                   description="估值分位：待 Tushare 回填 daily_basic" style="margin-bottom: 16px" />
          <div v-if="dailyBasic.length">
            <a-card title="PE / PB 趋势（近250日）" size="small" style="margin-bottom: 16px">
              <div ref="pePbEl" style="width: 100%; height: 320px"></div>
            </a-card>
            <a-table :data="dailyBasic" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="交易日" data-index="trade_date" />
                <a-table-column title="PE" data-index="pe">
                  <template #cell="{ record }">{{ fmtNum(record.pe) }}</template>
                </a-table-column>
                <a-table-column title="PE(TTM)" data-index="pe_ttm">
                  <template #cell="{ record }">{{ fmtNum(record.pe_ttm) }}</template>
                </a-table-column>
                <a-table-column title="PB" data-index="pb">
                  <template #cell="{ record }">{{ fmtNum(record.pb) }}</template>
                </a-table-column>
                <a-table-column title="PS" data-index="ps">
                  <template #cell="{ record }">{{ fmtNum(record.ps) }}</template>
                </a-table-column>
                <a-table-column title="股息率" data-index="dv_ratio">
                  <template #cell="{ record }">{{ fmtPct(record.dv_ratio) }}</template>
                </a-table-column>
                <a-table-column title="换手率" data-index="turnover_rate">
                  <template #cell="{ record }">{{ fmtPct(record.turnover_rate) }}</template>
                </a-table-column>
                <a-table-column title="总市值" data-index="total_mv">
                  <template #cell="{ record }">{{ fmtMoney((record.total_mv ?? 0) * 1e4) }}</template>
                </a-table-column>
                <a-table-column title="流通市值" data-index="circ_mv">
                  <template #cell="{ record }">{{ fmtMoney((record.circ_mv ?? 0) * 1e4) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="dividend" title="分红送股">
          <div v-if="dividend.length">
            <a-table :data="dividend" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="公告日" data-index="ann_date" />
                <a-table-column title="分红年度" data-index="end_date" />
                <a-table-column title="进度" data-index="div_proc" />
                <a-table-column title="每股分红" data-index="cash_div">
                  <template #cell="{ record }">{{ record.cash_div != null ? fmtNum(record.cash_div) + ' 元/股' : '--' }}</template>
                </a-table-column>
                <a-table-column title="每股送股" data-index="stk_div">
                  <template #cell="{ record }">{{ record.stk_div != null ? fmtNum(record.stk_div) + ' 股/股' : '--' }}</template>
                </a-table-column>
                <a-table-column title="每股转增" data-index="stk_bo_rate">
                  <template #cell="{ record }">{{ record.stk_bo_rate != null ? fmtNum(record.stk_bo_rate) + ' 股/股' : '--' }}</template>
                </a-table-column>
                <a-table-column title="股权登记日" data-index="record_date" />
                <a-table-column title="除权除息日" data-index="ex_date" />
                <a-table-column title="派息日" data-index="pay_date" />
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="forecast" title="业绩预告">
          <div v-if="forecast.length">
            <a-table :data="forecast" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="公告日" data-index="ann_date" />
                <a-table-column title="报告期" data-index="end_date" />
                <a-table-column title="预告类型" data-index="ptype">
                  <template #cell="{ record }">
                    <a-tag :color="ptypeColor(record.ptype)">{{ record.ptype }}</a-tag>
                  </template>
                </a-table-column>
                <a-table-column title="净利润下限" data-index="net_profit_min">
                  <template #cell="{ record }">{{ fmtMoney((record.net_profit_min ?? 0) * 1e4) }}</template>
                </a-table-column>
                <a-table-column title="净利润上限" data-index="net_profit_max">
                  <template #cell="{ record }">{{ fmtMoney((record.net_profit_max ?? 0) * 1e4) }}</template>
                </a-table-column>
                <a-table-column title="上年同期" data-index="last_parent_net">
                  <template #cell="{ record }">{{ fmtMoney((record.last_parent_net ?? 0) * 1e4) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="express" title="业绩快报">
          <div v-if="express.length">
            <a-table :data="express" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="公告日" data-index="ann_date" />
                <a-table-column title="报告期" data-index="end_date" />
                <a-table-column title="营收" data-index="revenue">
                  <template #cell="{ record }">{{ fmtMoney(record.revenue) }}</template>
                </a-table-column>
                <a-table-column title="净利润" data-index="net_profit">
                  <template #cell="{ record }">{{ fmtMoney(record.net_profit) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="moneyflow" title="资金流向">
          <div v-if="moneyflow.length">
            <a-card title="主力净流入（近60日，万元）" size="small" style="margin-bottom: 16px">
              <div ref="mfEl" style="width: 100%; height: 320px"></div>
            </a-card>
            <a-table :data="moneyflow" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="交易日" data-index="trade_date" />
                <a-table-column title="净流入(万)" data-index="net_mf_amount">
                  <template #cell="{ record }">
                    <span :style="{ color: (record.net_mf_amount ?? 0) >= 0 ? '#ef232a' : '#14b143' }">
                      {{ fmtNum(record.net_mf_amount) }}
                    </span>
                  </template>
                </a-table-column>
                <a-table-column title="小单净(万)">
                  <template #cell="{ record }">{{ fmtNum((record.buy_sm_amount ?? 0) - (record.sell_sm_amount ?? 0)) }}</template>
                </a-table-column>
                <a-table-column title="中单净(万)">
                  <template #cell="{ record }">{{ fmtNum((record.buy_md_amount ?? 0) - (record.sell_md_amount ?? 0)) }}</template>
                </a-table-column>
                <a-table-column title="大单净(万)">
                  <template #cell="{ record }">{{ fmtNum((record.buy_lg_amount ?? 0) - (record.sell_lg_amount ?? 0)) }}</template>
                </a-table-column>
                <a-table-column title="特大单净(万)">
                  <template #cell="{ record }">{{ fmtNum((record.buy_elg_amount ?? 0) - (record.sell_elg_amount ?? 0)) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="suspend" title="停复牌">
          <div v-if="suspend.length">
            <a-table :data="suspend" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="停牌日期" data-index="suspend_date" />
                <a-table-column title="复牌日期" data-index="resume_date" />
                <a-table-column title="停牌原因" data-index="suspend_reason" />
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <!-- 新增：Tushare 全量接口（懒加载） -->
        <a-tab-pane key="mainbz" title="主营业务">
          <div v-if="mainbz.length">
            <a-space style="margin-bottom: 12px">
              <span>报告期：</span>
              <a-select v-model="mainbzPeriod" style="width: 160px">
                <a-option v-for="p in mainbzPeriods" :key="p" :value="p">{{ p }}</a-option>
              </a-select>
            </a-space>
            <a-table :data="mainbzFiltered" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="业务项目" data-index="bz_item" :ellipsis="true" :tooltip="true" />
                <a-table-column title="收入(万元)" data-index="bz_sales">
                  <template #cell="{ record }">{{ fmtNum(record.bz_sales) }}</template>
                </a-table-column>
                <a-table-column title="利润(万元)" data-index="bz_profit">
                  <template #cell="{ record }">{{ fmtNum(record.bz_profit) }}</template>
                </a-table-column>
                <a-table-column title="成本(万元)" data-index="bz_cost">
                  <template #cell="{ record }">{{ fmtNum(record.bz_cost) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="company-detail" title="公司详情">
          <a-descriptions
            v-if="companyDetail"
            :column="2"
            bordered
            size="small"
            title="公司详细信息"
          >
            <a-descriptions-item label="董事长">{{ companyDetail.chairman || '--' }}</a-descriptions-item>
            <a-descriptions-item label="总经理">{{ companyDetail.manager || '--' }}</a-descriptions-item>
            <a-descriptions-item label="董秘">{{ companyDetail.secretary || '--' }}</a-descriptions-item>
            <a-descriptions-item label="注册资本(万元)">{{ fmtNum(companyDetail.reg_capital) }}</a-descriptions-item>
            <a-descriptions-item label="成立日期">{{ companyDetail.setup_date || '--' }}</a-descriptions-item>
            <a-descriptions-item label="省份 / 城市">{{ [companyDetail.province, companyDetail.city].filter(Boolean).join(' / ') || '--' }}</a-descriptions-item>
            <a-descriptions-item label="员工人数">{{ fmtNum(companyDetail.employees) }}</a-descriptions-item>
            <a-descriptions-item label="官网">
              <a-link v-if="companyDetail.website" :href="'http://' + companyDetail.website" target="_blank">{{ companyDetail.website }}</a-link>
              <span v-else>--</span>
            </a-descriptions-item>
            <a-descriptions-item label="电子邮箱">{{ companyDetail.email || '--' }}</a-descriptions-item>
            <a-descriptions-item label="办公地址">{{ companyDetail.office || '--' }}</a-descriptions-item>
            <a-descriptions-item label="主营业务" :span="2">{{ companyDetail.main_business || '--' }}</a-descriptions-item>
            <a-descriptions-item label="经营范围" :span="2">{{ companyDetail.business_scope || '--' }}</a-descriptions-item>
            <a-descriptions-item label="公司简介" :span="2">{{ companyDetail.introduction || '--' }}</a-descriptions-item>
          </a-descriptions>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="governance" title="治理">
          <a-card title="管理层" size="small" style="margin-bottom: 16px">
            <div v-if="managers.length">
              <a-table :data="managers" :pagination="{ pageSize: 15 }" size="small">
                <template #columns>
                  <a-table-column title="姓名" data-index="name" :width="100" />
                  <a-table-column title="职务" data-index="title" :ellipsis="true" :tooltip="true" />
                  <a-table-column title="性别" data-index="gender" :width="70" />
                  <a-table-column title="学历" data-index="edu" :width="90" />
                  <a-table-column title="任期" :width="220">
                    <template #cell="{ record }">
                      {{ record.begin_date || '--' }} ~ {{ record.end_date || '至今' }}
                    </template>
                  </a-table-column>
                  <a-table-column title="简历">
                    <template #cell="{ record }">
                      <a-tooltip v-if="record.resume" :content="record.resume" position="left">
                        <a-link>查看</a-link>
                      </a-tooltip>
                      <span v-else>--</span>
                    </template>
                  </a-table-column>
                </template>
              </a-table>
            </div>
            <a-empty v-else description="暂无数据" />
          </a-card>
          <a-card title="审计意见" size="small" style="margin-bottom: 16px">
            <div v-if="finaAudit.length">
              <a-table :data="finaAudit" :pagination="{ pageSize: 10 }" size="small">
                <template #columns>
                  <a-table-column title="报告期" data-index="end_date" :width="120" />
                  <a-table-column title="审计结果" data-index="audit_result" :ellipsis="true" :tooltip="true" />
                  <a-table-column title="审计费用(万元)" data-index="audit_fees">
                    <template #cell="{ record }">{{ fmtNum(record.audit_fees) }}</template>
                  </a-table-column>
                  <a-table-column title="事务所" data-index="audit_agency" :ellipsis="true" :tooltip="true" />
                </template>
              </a-table>
            </div>
            <a-empty v-else description="暂无数据" />
          </a-card>
          <a-card title="曾用名" size="small">
            <a-timeline v-if="namechange.length">
              <a-timeline-item
                v-for="n in [...namechange].reverse()"
                :key="n.start_date + n.old_name"
                :label="n.start_date"
              >
                {{ n.old_name }}
                <span style="color: #86909c; margin-left: 8px">{{ n.start_date }} ~ {{ n.end_date || '至今' }}</span>
              </a-timeline-item>
            </a-timeline>
            <a-empty v-else description="暂无数据" />
          </a-card>
        </a-tab-pane>
        <a-tab-pane key="margin-detail" title="两融">
          <div v-if="marginDetail.length">
            <a-card title="融资 / 融券余额（近60日，万元）" size="small" style="margin-bottom: 16px">
              <div ref="marginDetailEl" style="width: 100%; height: 320px"></div>
            </a-card>
            <a-table :data="marginDetail" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="交易日" data-index="trade_date" :width="120" />
                <a-table-column title="融资余额(万)" data-index="rzye">
                  <template #cell="{ record }">{{ fmtNum(record.rzye) }}</template>
                </a-table-column>
                <a-table-column title="融券余额(万)" data-index="rqye">
                  <template #cell="{ record }">{{ fmtNum(record.rqye) }}</template>
                </a-table-column>
                <a-table-column title="融资融券余额(万)" data-index="rzrqye">
                  <template #cell="{ record }">{{ fmtNum(record.rzrqye) }}</template>
                </a-table-column>
                <a-table-column title="融券余量(万股)" data-index="rqyl">
                  <template #cell="{ record }">{{ fmtNum(record.rqyl) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="disclosure" title="披露计划">
          <div v-if="disclosure.length">
            <a-table :data="disclosure" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="报告期" data-index="end_date" :width="120" />
                <a-table-column title="公告日" data-index="ann_date" :width="120" />
                <a-table-column title="预约披露日" data-index="pre_date" :width="120" />
                <a-table-column title="实际披露日" data-index="actual_date" :width="120" />
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="stk-limit" title="涨跌停">
          <div v-if="stkLimit.length">
            <a-table :data="stkLimit" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="交易日" data-index="trade_date" :width="120" />
                <a-table-column title="昨收" data-index="pre_close">
                  <template #cell="{ record }">{{ fmtNum(record.pre_close) }}</template>
                </a-table-column>
                <a-table-column title="涨停价" data-index="up_limit">
                  <template #cell="{ record }">
                    <span style="color: #ef232a">{{ fmtNum(record.up_limit) }}</span>
                  </template>
                </a-table-column>
                <a-table-column title="跌停价" data-index="down_limit">
                  <template #cell="{ record }">
                    <span style="color: #14b143">{{ fmtNum(record.down_limit) }}</span>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="share-float" title="限售解禁">
          <div v-if="shareFloat.length">
            <a-alert v-if="futureFloatStat.shares > 0" type="warning" style="margin-bottom: 12px">
              未来1年待解禁 {{ fmtYi(futureFloatStat.shares) }} 股，占总股本 {{ futureFloatStat.ratio.toFixed(2) }}%
            </a-alert>
            <a-table :data="shareFloat" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="解禁日期" data-index="float_date" :width="120">
                  <template #cell="{ record }">
                    {{ record.float_date }}
                    <a-tag v-if="record.is_future" color="orange" size="small" style="margin-left: 6px">待解禁</a-tag>
                  </template>
                </a-table-column>
                <a-table-column title="解禁数量(股)" data-index="float_share">
                  <template #cell="{ record }">{{ fmtNum(record.float_share) }}</template>
                </a-table-column>
                <a-table-column title="占总股本比(%)" data-index="float_ratio">
                  <template #cell="{ record }">{{ record.float_ratio != null ? Number(record.float_ratio).toFixed(2) : '-' }}</template>
                </a-table-column>
                <a-table-column title="股东名称" data-index="holder_name" :width="200" ellipsis tooltip />
                <a-table-column title="股份类型" data-index="share_type" :width="140" />
                <a-table-column title="公告日" data-index="ann_date" :width="120" />
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="block-trade" title="大宗交易">
          <div v-if="blockTrade.length">
            <a-table :data="blockTrade" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="日期" data-index="trade_date" :width="110" />
                <a-table-column title="成交价" data-index="price">
                  <template #cell="{ record }">{{ fmtNum(record.price) }}</template>
                </a-table-column>
                <a-table-column title="溢价率(%)" data-index="premium" :width="110">
                  <template #cell="{ record }">
                    <span v-if="record.premium != null"
                          :style="{ color: record.premium > 0 ? '#ef232a' : record.premium < 0 ? '#14b143' : undefined }">
                      {{ record.premium > 0 ? '+' : '' }}{{ record.premium.toFixed(2) }}
                    </span>
                    <span v-else>-</span>
                  </template>
                </a-table-column>
                <a-table-column title="成交量(万股)" data-index="vol">
                  <template #cell="{ record }">{{ fmtNum(record.vol) }}</template>
                </a-table-column>
                <a-table-column title="成交额(万元)" data-index="amount">
                  <template #cell="{ record }">{{ fmtNum(record.amount) }}</template>
                </a-table-column>
                <a-table-column title="买方" data-index="buyer" :width="160" ellipsis tooltip />
                <a-table-column title="卖方" data-index="seller" :width="160" ellipsis tooltip />
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="repurchase" title="股票回购">
          <div v-if="repurchase.length">
            <a-table :data="repurchase" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="公告日" data-index="ann_date" :width="110" />
                <a-table-column title="进度" data-index="proc" :width="140" />
                <a-table-column title="回购数量(股)" data-index="vol">
                  <template #cell="{ record }">{{ fmtNum(record.vol) }}</template>
                </a-table-column>
                <a-table-column title="回购金额(元)" data-index="amount">
                  <template #cell="{ record }">{{ fmtNum(record.amount) }}</template>
                </a-table-column>
                <a-table-column title="价格下限" data-index="price_low">
                  <template #cell="{ record }">{{ fmtNum(record.price_low) }}</template>
                </a-table-column>
                <a-table-column title="价格上限" data-index="price_high">
                  <template #cell="{ record }">{{ fmtNum(record.price_high) }}</template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="pledge-detail" title="质押明细">
          <div v-if="pledgeDetail.length">
            <a-table :data="pledgeDetail" :pagination="{ pageSize: 20 }" size="small">
              <template #columns>
                <a-table-column title="公告日" data-index="ann_date" :width="110" />
                <a-table-column title="出质人" data-index="holder_name" :width="180" ellipsis tooltip />
                <a-table-column title="质押数量(万股)" data-index="pledge_amount">
                  <template #cell="{ record }">{{ fmtNum(record.pledge_amount) }}</template>
                </a-table-column>
                <a-table-column title="起始日" data-index="start_date" :width="110" />
                <a-table-column title="到期日" data-index="end_date" :width="110" />
                <a-table-column title="已解押" data-index="is_release" :width="90" />
              </template>
            </a-table>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="cyq" title="筹码分布">
          <div v-if="cyq.length">
            <a-row :gutter="16" style="margin-bottom: 12px">
              <a-col :span="8">
                <a-statistic title="最新获利盘比例(%)" :value="cyqLatest.winner_rate != null ? Number(cyqLatest.winner_rate).toFixed(2) : '-'" />
              </a-col>
              <a-col :span="8">
                <a-statistic title="平均成本" :value="fmtNum(cyqLatest.weight_avg)" />
              </a-col>
              <a-col :span="8">
                <a-statistic title="90%成本区间" :value="cyqCostRange" />
              </a-col>
            </a-row>
            <div ref="cyqEl" style="width: 100%; height: 300px"></div>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
        <a-tab-pane key="hk-hold" title="港股通持股">
          <div v-if="hkHold.length">
            <div ref="hkHoldEl" style="width: 100%; height: 300px"></div>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-tab-pane>
      </a-tabs>
    </a-spin>
  </a-card>
</template>

<script setup>
import { getJSON } from '../../../platform/utils/api.js'
import { ref, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconLeft } from '@arco-design/web-vue/es/icon'
import { echarts, initChart } from '../../../platform/utils/echarts-theme.js'
import WatchStar from '../components/WatchStar.vue'
import FinTable from '../components/FinTable.vue'
import { fmtDateLocal as fmt } from '../../../platform/utils/date.js'

const props = defineProps({ symbol: String })
const route = useRoute()
const stockName = computed(() => route.query.name || '')
const title = computed(() => `${stockName.value} ${props.symbol}`.trim())

const chartEl = ref(null)
const incomeEl = ref(null)
const roeEl = ref(null)
const pePbEl = ref(null)
const mfEl = ref(null)
const loading = ref(false)
let chart = null
let incomeChart = null
let roeChart = null
let pePbChart = null
let mfChart = null

const today = new Date()
const lastYear = new Date(today)
lastYear.setFullYear(today.getFullYear() - 1)
const range = ref([fmt(lastYear), fmt(today)])

const company = ref({})
const financials = ref({ income: [], balance: [], cashflow: [], indicator: [] })
const business = ref([])
const holders = ref([])
const trades = ref([])
// Tushare 增量数据
const dailyBasic = ref([])
const dailyBasicLoaded = ref(false)
const valuation = ref(null)
let valPeEl = null
let valPbEl = null
let valPeChart = null
let valPbChart = null
const valItems = computed(() => {
  if (!valuation.value || !valuation.value.found) return []
  return [
    { key: 'pe', label: 'PE-TTM', stat: valuation.value.pe_ttm },
    { key: 'pb', label: 'PB', stat: valuation.value.pb },
  ].filter((i) => i.stat && i.stat.found)
})
const dividend = ref([])
const forecast = ref([])
const express = ref([])
const moneyflow = ref([])
const suspend = ref([])
// Tushare 全量接口（懒加载）
const mainbz = ref([])
const mainbzPeriod = ref('')
const mainbzPeriods = computed(() =>
  [...new Set(mainbz.value.map((r) => r.end_date))].sort().reverse()
)
const mainbzFiltered = computed(() =>
  mainbzPeriod.value ? mainbz.value.filter((r) => r.end_date === mainbzPeriod.value) : mainbz.value
)
const companyDetail = ref(null)
const managers = ref([])
const finaAudit = ref([])
const namechange = ref([])
const marginDetail = ref([])
const disclosure = ref([])
const stkLimit = ref([])
const shareFloat = ref([])
const blockTrade = ref([])
const repurchase = ref([])
const pledgeDetail = ref([])
const cyq = ref([])
const hkHold = ref([])
const cyqEl = ref(null)
const hkHoldEl = ref(null)
let cyqChart = null
let hkHoldChart = null
const cyqLatest = computed(() => (cyq.value.length ? cyq.value[0] : {}))
const cyqCostRange = computed(() => {
  const c = cyqLatest.value
  if (c.cost_5pct == null || c.cost_95pct == null) return '-'
  return `${fmtNum(c.cost_5pct)} ~ ${fmtNum(c.cost_95pct)}`
})
// 未来1年待解禁统计
const futureFloatStat = computed(() => {
  const oneYearLater = new Date()
  oneYearLater.setFullYear(oneYearLater.getFullYear() + 1)
  const cutoff = fmt(oneYearLater)
  let shares = 0, ratio = 0
  for (const r of shareFloat.value) {
    if (r.is_future && r.float_date <= cutoff) {
      shares += Number(r.float_share) || 0
      ratio += Number(r.float_ratio) || 0
    }
  }
  return { shares, ratio }
})
// 股数转亿股显示
function fmtYi(v) {
  if (v == null) return '-'
  const yi = Number(v) / 1e8
  return yi >= 0.01 ? `${yi.toFixed(2)}亿` : `${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}
const marginDetailEl = ref(null)
let marginDetailChart = null
const extraLoaded = {}
const activeTab = ref('income')

function fmtNum(v) {
  if (v == null) return '--'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function fmtMoney(v) {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return fmtNum(v)
}
function fmtPct(v) {
  if (v == null) return '--'
  return Number(v).toFixed(2) + '%'
}
function ptypeColor(t) {
  if (!t) return 'gray'
  if (t.includes('预增')) return 'red'
  if (t.includes('预减')) return 'green'
  if (t.includes('扭亏')) return 'blue'
  return 'gray'
}

let loadSeq = 0
async function loadAll() {
  if (!range.value || range.value.length !== 2) return
  const mySeq = ++loadSeq
  const alive = () => mySeq === loadSeq
  loading.value = true
  try {
    const [from, to] = range.value
    const q = new URLSearchParams({ market: 'cn', symbol: props.symbol })
    const [comp, bars, macd] = await Promise.all([
      getJSON(`/api/stock/company?${q}`),
      getJSON(`/api/stock/bars?${q}&from=${from}&to=${to}`),
      getJSON(`/api/stock/tech?${q}&from=${from}&to=${to}&indicator=macd`),
    ])
    if (!alive()) return
    company.value = comp
    renderChart(bars, macd)

    const [income, balance, cashflow, indicator, biz, hol, trd] = await Promise.all([
      getJSON(`/api/stock/financials?${q}&type=income`),
      getJSON(`/api/stock/financials?${q}&type=balance`),
      getJSON(`/api/stock/financials?${q}&type=cashflow`),
      getJSON(`/api/stock/financials?${q}&type=indicator`),
      getJSON(`/api/stock/business?${q}`),
      getJSON(`/api/stock/holders?${q}&type=top10`),
      getJSON(`/api/stock/holder-trades?${q}`),
    ])
    if (!alive()) return
    financials.value = { income, balance, cashflow, indicator }
    business.value = biz
    holders.value = hol
    trades.value = trd
    await nextTick()
    if (!alive()) return
    renderIncomeChart()
    renderRoeChart()

    // Tushare 增量数据（并行拉取，与日期范围无关）
    const [db250, div, fc, ex, mf, sp, val] = await Promise.all([
      getJSON(`/api/stock/daily-basic?${q}&limit=250`),
      getJSON(`/api/stock/dividend?${q}`),
      getJSON(`/api/stock/forecast?${q}`),
      getJSON(`/api/stock/express?${q}`),
      getJSON(`/api/stock/moneyflow?${q}&limit=60`),
      getJSON(`/api/stock/suspend?${q}`),
      getJSON(`/api/stock/valuation-quantile?${q}`).catch(() => ({ found: false })),
    ])
    if (!alive()) return
    dailyBasic.value = db250
    dailyBasicLoaded.value = true
    valuation.value = val
    dividend.value = div
    forecast.value = fc
    express.value = ex
    moneyflow.value = mf
    suspend.value = sp
    await nextTick()
    if (!alive()) return
    renderPePbChart()
    renderMfChart()
    renderValuationCharts()
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    if (alive()) loading.value = false
  }
}

function renderChart(bars, macd) {
  if (!bars.length) {
    chart && chart.clear()
    return
  }
  const dates = bars.map((b) => b.date)
  const candles = bars.map((b) => [b.open, b.close, b.low, b.high])
  // macd 返回的 dates 与 bars 对齐（同 from/to）
  const macdMap = new Map(macd.dates.map((d, i) => [d, macd.values[i]]))
  const dif = dates.map((d) => (macdMap.get(d) || [])[0] ?? '-')
  const dea = dates.map((d) => (macdMap.get(d) || [])[1] ?? '-')
  const hist = dates.map((d) => (macdMap.get(d) || [])[2] ?? '-')
  chart.setOption({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', 'DIF', 'DEA', 'MACD'] },
    grid: [
      { left: '8%', right: '8%', top: '8%', height: '52%' },
      { left: '8%', right: '8%', top: '66%', height: '22%' },
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, axisLabel: { hideOverlap: true } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [{ scale: true, splitArea: { show: true } }, { scale: true, gridIndex: 1 }],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
      { type: 'slider', xAxisIndex: [0, 1], top: '92%' },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: candles,
        itemStyle: { color: '#e5484d', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' },
      },
      { name: 'DIF', type: 'line', data: dif, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 1, yAxisIndex: 1 },
      { name: 'DEA', type: 'line', data: dea, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 1, yAxisIndex: 1 },
      {
        name: 'MACD', type: 'bar', data: hist, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: (p) => (p.value > 0 ? '#ef232a' : '#14b143') },
      },
    ],
  }, true)
}

function renderIncomeChart() {
  if (!incomeEl.value || !financials.value.income.length) return
  incomeChart && incomeChart.dispose()
  incomeChart = initChart(incomeEl.value)
  // 按报告期升序
  const rows = [...financials.value.income].reverse()
  const dates = rows.map((r) => r.report_date)
  const revenue = rows.map((r) => (r.revenue != null ? +(r.revenue / 1e8).toFixed(2) : '-'))
  const profit = rows.map((r) => (r.net_profit != null ? +(r.net_profit / 1e8).toFixed(2) : '-'))
  incomeChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['营收(亿)', '净利润(亿)'] },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: { type: 'value', name: '亿元' },
    series: [
      { name: '营收(亿)', type: 'bar', data: revenue, itemStyle: { color: '#2f6bff' } },
      { name: '净利润(亿)', type: 'line', data: profit, smooth: true, showSymbol: false,
        lineStyle: { width: 2 }, itemStyle: { color: '#e5484d' } },
    ],
  })
}

function renderRoeChart() {
  if (!roeEl.value || !financials.value.indicator.length) return
  roeChart && roeChart.dispose()
  roeChart = initChart(roeEl.value)
  const rows = [...financials.value.indicator].reverse()
  const dates = rows.map((r) => r.report_date)
  const pick = (k) => rows.map((r) => (r[k] != null ? +Number(r[k]).toFixed(2) : '-'))
  roeChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['ROE(%)', '毛利率(%)', '净利率(%)'] },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: { type: 'value', name: '%' },
    series: [
      { name: 'ROE(%)', type: 'line', data: pick('roe'), smooth: true, showSymbol: false, lineStyle: { width: 2 } },
      { name: '毛利率(%)', type: 'line', data: pick('gross_margin'), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: '净利率(%)', type: 'line', data: pick('net_margin'), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
    ],
  })
}

function onResize() {
  chart && chart.resize()
  incomeChart && incomeChart.resize()
  roeChart && roeChart.resize()
  pePbChart && pePbChart.resize()
  mfChart && mfChart.resize()
  marginDetailChart && marginDetailChart.resize()
  valPeChart && valPeChart.resize()
  valPbChart && valPbChart.resize()
  cyqChart && cyqChart.resize()
  hkHoldChart && hkHoldChart.resize()
}

// 读取 / 恢复 tabs 导航条横向偏移（Arco 用 transform，不是 scrollLeft）
function getTabsNavList() {
  return document.querySelector('.company-tabs .arco-tabs-nav-tab-list')
}
function readTabsOffset() {
  const list = getTabsNavList()
  if (!list) return 0
  const m = /translateX\((-?\d+(?:\.\d+)?)px\)/.exec(list.style.transform || '')
  return m ? Math.abs(parseFloat(m[1])) : 0
}
function writeTabsOffset(px) {
  const list = getTabsNavList()
  if (!list) return
  list.style.transform = `translateX(${-Math.max(0, px)}px)`
}

// tab 切换后重算图表尺寸（隐藏 tab 内初始化的图表宽高为 0）；新 tab 懒加载数据
function onTabChange(key) {
  // 数据加载会触发布局/ResizeObserver；Arco auto 模式还会把 offset 置 0。
  // 先记下当前偏移，在 Arco 校正与内容刷新后再写回，避免导航条被弹回最左。
  const saved = readTabsOffset()
  const restore = () => writeTabsOffset(saved)
  setTimeout(restore, 0)
  nextTick(() => {
    pePbChart && pePbChart.resize()
    mfChart && mfChart.resize()
    marginDetailChart && marginDetailChart.resize()
    valPeChart && valPeChart.resize()
    valPbChart && valPbChart.resize()
  })
  if (key) ensureTabLoaded(key).finally(() => {
    nextTick(() => {
      // lazy-load 下首次点开 tab 时 div 刚挂载，补画其中的图表
      if (key === 'daily-basic') {
        renderPePbChart()
        renderValuationCharts()
      } else if (key === 'moneyflow') {
        renderMfChart()
      } else if (key === 'indicator') {
        renderRoeChart()
      } else if (key === 'income') {
        renderIncomeChart()
      }
      restore()
    })
    setTimeout(restore, 50)
  })
}

// 新增 tab 懒加载：只在首次切换到该 tab 时请求
async function ensureTabLoaded(key) {
  if (extraLoaded[key]) return
  extraLoaded[key] = true
  try {
    const q = new URLSearchParams({ market: 'cn', symbol: props.symbol })
    if (key === 'mainbz') {
      mainbz.value = await getJSON(`/api/stock/mainbz?${q}`)
      mainbzPeriod.value = mainbzPeriods.value[0] || ''
    } else if (key === 'company-detail') {
      companyDetail.value = await getJSON(`/api/stock/company-detail?${q}`)
    } else if (key === 'governance') {
      const [mg, au, nc] = await Promise.all([
        getJSON(`/api/stock/managers?${q}`),
        getJSON(`/api/stock/fina-audit?${q}`),
        getJSON(`/api/stock/namechange?${q}`),
      ])
      managers.value = mg
      finaAudit.value = au
      namechange.value = nc
    } else if (key === 'margin-detail') {
      marginDetail.value = await getJSON(`/api/stock/margin-detail?${q}&limit=60`)
    } else if (key === 'disclosure') {
      disclosure.value = await getJSON(`/api/stock/disclosure?${q}`)
    } else if (key === 'stk-limit') {
      stkLimit.value = await getJSON(`/api/stock/stk-limit?${q}&limit=60`)
    } else if (key === 'share-float') {
      shareFloat.value = await getJSON(`/api/stock/share-float?${q}`)
    } else if (key === 'block-trade') {
      blockTrade.value = await getJSON(`/api/stock/block-trade?${q}&limit=100`)
    } else if (key === 'repurchase') {
      repurchase.value = await getJSON(`/api/stock/repurchase?${q}`)
    } else if (key === 'pledge-detail') {
      pledgeDetail.value = await getJSON(`/api/stock/pledge-detail?${q}`)
    } else if (key === 'cyq') {
      cyq.value = await getJSON(`/api/stock/cyq?${q}&limit=250`)
    } else if (key === 'hk-hold') {
      hkHold.value = await getJSON(`/api/stock/hk-hold?${q}&limit=250`)
    }
  } catch (e) {
    extraLoaded[key] = false
    Message.error(`加载失败：${e.message}`)
  }
  await nextTick()
  if (key === 'margin-detail') renderMarginDetailChart()
  if (key === 'cyq') renderCyqChart()
  if (key === 'hk-hold') renderHkHoldChart()
}

function renderPePbChart() {
  if (!pePbEl.value || !dailyBasic.value.length) return
  pePbChart && pePbChart.dispose()
  pePbChart = initChart(pePbEl.value)
  // 按交易日升序
  const rows = [...dailyBasic.value].reverse()
  const dates = rows.map((r) => r.trade_date)
  const pick = (k) => rows.map((r) => (r[k] != null ? +Number(r[k]).toFixed(2) : '-'))
  pePbChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['PE', 'PB'] },
    grid: { left: '8%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: 'PE' },
      { type: 'value', name: 'PB' },
    ],
    series: [
      { name: 'PE', type: 'line', data: pick('pe'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, yAxisIndex: 0 },
      { name: 'PB', type: 'line', data: pick('pb'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, yAxisIndex: 1 },
    ],
  })
}

function renderValuationCharts() {
  const rows = [...dailyBasic.value].reverse() // 交易日升序
  const dates = rows.map((r) => r.trade_date)
  const draw = (el, key, stat, name) => {
    if (!el) return null
    const c = initChart(el)
    const data = rows.map((r) => (r[key] != null && r[key] > 0 ? +Number(r[key]).toFixed(2) : '-'))
    const qline = (v, label, color) => ({
      yAxis: v, label: { formatter: label, fontSize: 10, color },
      lineStyle: { type: 'dashed', color, width: 1 },
    })
    c.setOption({
      animation: false,
      tooltip: { trigger: 'axis' },
      grid: { left: '10%', right: '6%', top: '10%', bottom: '14%' },
      xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
      yAxis: { type: 'value', name },
      series: [{
        name, type: 'line', data, smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 },
        markLine: {
          symbol: 'none',
          data: [
            qline(stat.q25, '25%', '#00b42a'),
            qline(stat.median, '中位', '#165dff'),
            qline(stat.q75, '75%', '#f53f3f'),
          ],
        },
      }],
    })
    return c
  }
  valPeChart && valPeChart.dispose()
  valPbChart && valPbChart.dispose()
  valPeChart = valPbChart = null
  for (const item of valItems.value) {
    const el = item.key === 'pe' ? valPeEl : valPbEl
    const c = draw(el, item.key === 'pe' ? 'pe_ttm' : 'pb', item.stat, item.label)
    if (item.key === 'pe') valPeChart = c
    else valPbChart = c
  }
}

function renderMfChart() {
  if (!mfEl.value || !moneyflow.value.length) return
  mfChart && mfChart.dispose()
  mfChart = initChart(mfEl.value)
  const rows = [...moneyflow.value].reverse()
  const dates = rows.map((r) => r.trade_date)
  const net = rows.map((r) => (r.net_mf_amount != null ? +Number(r.net_mf_amount).toFixed(2) : 0))
  mfChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['净流入(万元)'] },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: { type: 'value', name: '万元' },
    series: [
      {
        name: '净流入(万元)', type: 'bar', data: net,
        itemStyle: { color: (p) => (p.value >= 0 ? '#ef232a' : '#14b143') },
      },
    ],
  })
}

onMounted(() => {
  chart = initChart(chartEl.value)
  window.addEventListener('resize', onResize)
  loadAll()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  incomeChart && incomeChart.dispose()
  roeChart && roeChart.dispose()
  pePbChart && pePbChart.dispose()
  mfChart && mfChart.dispose()
  marginDetailChart && marginDetailChart.dispose()
  valPeChart && valPeChart.dispose()
  valPbChart && valPbChart.dispose()
  cyqChart && cyqChart.dispose()
  hkHoldChart && hkHoldChart.dispose()
})

function renderMarginDetailChart() {
  if (!marginDetailEl.value || !marginDetail.value.length) return
  marginDetailChart && marginDetailChart.dispose()
  marginDetailChart = initChart(marginDetailEl.value)
  const rows = [...marginDetail.value].reverse()
  const dates = rows.map((r) => r.trade_date)
  const pick = (k) => rows.map((r) => (r[k] != null ? +Number(r[k]).toFixed(2) : '-'))
  marginDetailChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['融资余额(万)', '融券余额(万)'] },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '融资(万)' },
      { type: 'value', name: '融券(万)' },
    ],
    series: [
      {
        name: '融资余额(万)', type: 'line', data: pick('rzye'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, itemStyle: { color: '#e5484d' },
      },
      {
        name: '融券余额(万)', type: 'line', data: pick('rqye'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, yAxisIndex: 1, itemStyle: { color: '#2f6bff' },
      },
    ],
  })
}

function renderCyqChart() {
  if (!cyqEl.value || !cyq.value.length) return
  cyqChart && cyqChart.dispose()
  cyqChart = initChart(cyqEl.value)
  const rows = [...cyq.value].reverse()
  const dates = rows.map((r) => r.trade_date)
  const pick = (k) => rows.map((r) => (r[k] != null ? +Number(r[k]).toFixed(2) : '-'))
  cyqChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['获利盘比例(%)', '平均成本', '50%成本'] },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '获利盘(%)' },
      { type: 'value', name: '成本' },
    ],
    series: [
      {
        name: '获利盘比例(%)', type: 'line', data: pick('winner_rate'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, itemStyle: { color: '#e5484d' },
      },
      {
        name: '平均成本', type: 'line', data: pick('weight_avg'), smooth: true, showSymbol: false,
        yAxisIndex: 1, lineStyle: { width: 1.5 }, itemStyle: { color: '#2f6bff' },
      },
      {
        name: '50%成本', type: 'line', data: pick('cost_50pct'), smooth: true, showSymbol: false,
        yAxisIndex: 1, lineStyle: { width: 1, type: 'dashed' }, itemStyle: { color: '#86909c' },
      },
    ],
  })
}

function renderHkHoldChart() {
  if (!hkHoldEl.value || !hkHold.value.length) return
  hkHoldChart && hkHoldChart.dispose()
  hkHoldChart = initChart(hkHoldEl.value)
  const rows = [...hkHold.value].reverse()
  const dates = rows.map((r) => r.trade_date)
  const pick = (k) => rows.map((r) => (r[k] != null ? +Number(r[k]).toFixed(2) : '-'))
  hkHoldChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['持股数量(股)', '持股占比(%)'] },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '持股(股)' },
      { type: 'value', name: '占比(%)' },
    ],
    series: [
      {
        name: '持股数量(股)', type: 'line', data: pick('vol'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, itemStyle: { color: '#e5484d' },
      },
      {
        name: '持股占比(%)', type: 'line', data: pick('ratio'), smooth: true, showSymbol: false,
        yAxisIndex: 1, lineStyle: { width: 1.5 }, itemStyle: { color: '#2f6bff' },
      },
    ],
  })
}
</script>

<style scoped>
.stock-head { overflow: hidden; }
.stock-head :deep(.arco-card-header) {
  background: linear-gradient(135deg, #1c2547 0%, #2a3560 100%);
  border-bottom: none !important;
  padding: 16px 20px;
}
.stock-head :deep(.arco-card-header-title) { color: #fff !important; }
.stock-title { font-size: 18px; font-weight: 700; letter-spacing: 0.03em; }
.stock-head :deep(.arco-btn) { border-color: rgba(255,255,255,0.25); color: #fff; background: rgba(255,255,255,0.08); }
.stock-head :deep(.arco-btn:hover) { background: rgba(255,255,255,0.16); }
</style>
