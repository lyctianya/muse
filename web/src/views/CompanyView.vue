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

      <!-- 财务 / 股东 Tabs -->
      <a-tabs>
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
      </a-tabs>
    </a-spin>
  </a-card>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, h } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconLeft } from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'

const props = defineProps({ symbol: String })
const route = useRoute()
const stockName = computed(() => route.query.name || '')
const title = computed(() => `${stockName.value} ${props.symbol}`.trim())

const chartEl = ref(null)
const loading = ref(false)
let chart = null

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

function onResize() { chart && chart.resize() }

onMounted(() => {
  chart = echarts.init(chartEl.value)
  window.addEventListener('resize', onResize)
  loadAll()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
})
</script>
