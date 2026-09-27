<template>
  <a-card>
    <template #title>
      <a-space>
        <a-button shape="circle" @click="$router.back()"><icon-left /></a-button>
        <span>{{ title }}</span>
        <a-tag>A股</a-tag>
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

      <!-- 财务 / 股东 Tabs -->
      <a-tabs @change="onTabChange">
        <a-tab-pane key="income" title="利润表">
          <fin-table :rows="financials.income" />
        </a-tab-pane>
        <a-tab-pane key="balance" title="资产负债表">
          <fin-table :rows="financials.balance" />
        </a-tab-pane>
        <a-tab-pane key="cashflow" title="现金流量表">
          <fin-table :rows="financials.cashflow" />
        </a-tab-pane>
        <a-tab-pane key="indicator" title="财务指标">
          <fin-table :rows="financials.indicator" />
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
              <a-table-column title="均价" data-index="price">
                <template #cell="{ record }">{{ fmtNum(record.price) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="daily-basic" title="每日指标">
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
      </a-tabs>
    </a-spin>
  </a-card>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, h, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconLeft } from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'

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
const fmt = (d) => d.toISOString().slice(0, 10)
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
const dividend = ref([])
const forecast = ref([])
const express = ref([])
const moneyflow = ref([])
const suspend = ref([])

// 通用财务表：把 data JSON 的键值对转成行
const FinTable = {
  props: ['rows'],
  setup(p) {
    const columns = computed(() => {
      if (!p.rows.length) return []
      const keys = Object.keys(p.rows[0].data || {})
      return [
        { title: '报告期', dataIndex: 'report_date', width: 120, fixed: 'left' },
        ...keys.slice(0, 12).map((k) => ({ title: k, dataIndex: `data.${k}`, width: 140 })),
      ]
    })
    return () =>
      p.rows.length
        ? h('a-table', { data: p.rows, pagination: { pageSize: 10 }, size: 'small', scroll: { x: 1600 } },
            { columns: () => columns.value.map((c) =>
              h('a-table-column', { title: c.title, dataIndex: c.dataIndex, width: c.width })) })
        : h('a-empty', { description: '暂无数据' })
  },
}
const finTable = FinTable

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

async function getJSON(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function loadAll() {
  if (!range.value || range.value.length !== 2) return
  loading.value = true
  try {
    const [from, to] = range.value
    const q = new URLSearchParams({ market: 'cn', symbol: props.symbol })
    const [comp, bars, macd] = await Promise.all([
      getJSON(`/api/company?${q}`),
      getJSON(`/api/bars?${q}&from=${from}&to=${to}`),
      getJSON(`/api/tech?${q}&from=${from}&to=${to}&indicator=macd`),
    ])
    company.value = comp
    renderChart(bars, macd)

    const [income, balance, cashflow, indicator, biz, hol, trd] = await Promise.all([
      getJSON(`/api/financials?${q}&type=income`),
      getJSON(`/api/financials?${q}&type=balance`),
      getJSON(`/api/financials?${q}&type=cashflow`),
      getJSON(`/api/financials?${q}&type=indicator`),
      getJSON(`/api/business?${q}`),
      getJSON(`/api/holders?${q}&type=top10`),
      getJSON(`/api/holder-trades?${q}`),
    ])
    financials.value = { income, balance, cashflow, indicator }
    business.value = biz
    holders.value = hol
    trades.value = trd
    await nextTick()
    renderIncomeChart()
    renderRoeChart()

    // Tushare 增量数据（并行拉取，与日期范围无关）
    const [db250, div, fc, ex, mf, sp] = await Promise.all([
      getJSON(`/api/daily-basic?${q}&limit=250`),
      getJSON(`/api/dividend?${q}`),
      getJSON(`/api/forecast?${q}`),
      getJSON(`/api/express?${q}`),
      getJSON(`/api/moneyflow?${q}&limit=60`),
      getJSON(`/api/suspend?${q}`),
    ])
    dailyBasic.value = db250
    dividend.value = div
    forecast.value = fc
    express.value = ex
    moneyflow.value = mf
    suspend.value = sp
    await nextTick()
    renderPePbChart()
    renderMfChart()
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
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
        itemStyle: { color: '#ef232a', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' },
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
  incomeChart = echarts.init(incomeEl.value)
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
      { name: '营收(亿)', type: 'bar', data: revenue, itemStyle: { color: '#165dff' } },
      { name: '净利润(亿)', type: 'line', data: profit, smooth: true, showSymbol: false,
        lineStyle: { width: 2 }, itemStyle: { color: '#ef232a' } },
    ],
  })
}

function renderRoeChart() {
  if (!roeEl.value || !financials.value.indicator.length) return
  roeChart && roeChart.dispose()
  roeChart = echarts.init(roeEl.value)
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
}

// tab 切换后重算图表尺寸（隐藏 tab 内初始化的图表宽高为 0）
function onTabChange() {
  nextTick(() => {
    pePbChart && pePbChart.resize()
    mfChart && mfChart.resize()
  })
}

function renderPePbChart() {
  if (!pePbEl.value || !dailyBasic.value.length) return
  pePbChart && pePbChart.dispose()
  pePbChart = echarts.init(pePbEl.value)
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

function renderMfChart() {
  if (!mfEl.value || !moneyflow.value.length) return
  mfChart && mfChart.dispose()
  mfChart = echarts.init(mfEl.value)
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
  chart = echarts.init(chartEl.value)
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
})
</script>
