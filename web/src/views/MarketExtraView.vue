<template>
  <a-card title="市场深度数据（A股）" :loading="globalLoading">
    <a-tabs @change="onTabChange">
      <!-- 1. 指数行情 -->
      <a-tab-pane key="index" title="指数行情">
        <a-space style="margin-bottom: 12px">
          <a-select v-model="indexCode" style="width: 180px" @change="loadIndex">
            <a-option v-for="o in indexOptions" :key="o.code" :value="o.code">{{ o.label }}</a-option>
          </a-select>
          <a-range-picker v-model="indexRange" value-format="YYYY-MM-DD" style="width: 280px" @change="loadIndex" />
        </a-space>
        <div v-if="indexBars.length" ref="indexEl" style="width: 100%; height: 480px"></div>
        <a-empty v-else description="暂无数据" />
      </a-tab-pane>

      <!-- 2. 龙虎榜 -->
      <a-tab-pane key="toplist" title="龙虎榜">
        <a-space style="margin-bottom: 12px">
          <span>交易日：</span>
          <a-date-picker v-model="toplistDate" value-format="YYYY-MM-DD" @change="loadToplist" />
        </a-space>
        <div v-if="toplist.length">
          <a-table :data="toplist" :pagination="{ pageSize: 20 }" size="small"
                   row-key="symbol" v-model:expanded-row-keys="toplistExpanded"
                   @expand="onToplistExpand">
            <template #columns>
              <a-table-column title="代码" data-index="symbol" :width="110" />
              <a-table-column title="名称" data-index="name" :ellipsis="true" />
              <a-table-column title="收盘价" data-index="close" :width="100">
                <template #cell="{ record }">{{ fmtNum(record.close) }}</template>
              </a-table-column>
              <a-table-column title="涨跌幅" data-index="pct_change" :width="100">
                <template #cell="{ record }">
                  <span :style="{ color: (record.pct_change ?? 0) >= 0 ? '#ef232a' : '#14b143' }">
                    {{ record.pct_change != null ? Number(record.pct_change).toFixed(2) + '%' : '--' }}
                  </span>
                </template>
              </a-table-column>
              <a-table-column title="换手率" data-index="turnover_rate" :width="90">
                <template #cell="{ record }">{{ fmtPct(record.turnover_rate) }}</template>
              </a-table-column>
              <a-table-column title="龙虎榜净额(万)" data-index="net_amount" :width="140">
                <template #cell="{ record }">
                  <span :style="{ color: (record.net_amount ?? 0) >= 0 ? '#ef232a' : '#14b143' }">
                    {{ fmtNum(record.net_amount) }}
                  </span>
                </template>
              </a-table-column>
              <a-table-column title="上榜理由" data-index="reason" :ellipsis="true" :tooltip="true" />
            </template>
            <template #expand-row="{ record }">
              <div v-if="topinstLoading[topinstKey(record.symbol)]" style="padding: 12px; color: #86909c">
                机构明细加载中…
              </div>
              <a-table v-else :data="topinstCache[topinstKey(record.symbol)] || []"
                       :pagination="{ pageSize: 10 }" size="mini">
                <template #columns>
                  <a-table-column title="交易日" data-index="trade_date" :width="110" />
                  <a-table-column title="方向" data-index="side" :width="80">
                    <template #cell="{ record: r }">
                      <a-tag size="small" :color="r.side === '买方' ? 'red' : 'green'">{{ r.side }}</a-tag>
                    </template>
                  </a-table-column>
                  <a-table-column title="营业部" data-index="exalter" :ellipsis="true" :tooltip="true" />
                  <a-table-column title="买入(万)" data-index="buy" :width="120">
                    <template #cell="{ record: r }">{{ fmtNum(r.buy) }}</template>
                  </a-table-column>
                  <a-table-column title="卖出(万)" data-index="sell" :width="120">
                    <template #cell="{ record: r }">{{ fmtNum(r.sell) }}</template>
                  </a-table-column>
                  <a-table-column title="净买入(万)" data-index="net_buy" :width="130">
                    <template #cell="{ record: r }">
                      <span :style="{ color: (r.net_buy ?? 0) >= 0 ? '#ef232a' : '#14b143' }">
                        {{ fmtNum(r.net_buy) }}
                      </span>
                    </template>
                  </a-table-column>
                </template>
              </a-table>
            </template>
          </a-table>
        </div>
        <a-empty v-else description="暂无数据" />
      </a-tab-pane>

      <!-- 3. 北向资金 -->
      <a-tab-pane key="hsgt-flow" title="北向资金">
        <div v-if="hsgtFlow.length">
          <div ref="hsgtFlowEl" style="width: 100%; height: 380px"></div>
          <a-table :data="hsgtFlow" :pagination="{ pageSize: 20 }" size="small" style="margin-top: 16px">
            <template #columns>
              <a-table-column title="交易日" data-index="trade_date" :width="120" />
              <a-table-column title="北向资金(亿)" data-index="north_money">
                <template #cell="{ record }">{{ fmtNum(record.north_money) }}</template>
              </a-table-column>
              <a-table-column title="南向资金(亿)" data-index="south_money">
                <template #cell="{ record }">{{ fmtNum(record.south_money) }}</template>
              </a-table-column>
              <a-table-column title="沪股通(亿)" data-index="hgt">
                <template #cell="{ record }">{{ fmtNum(record.hgt) }}</template>
              </a-table-column>
              <a-table-column title="深股通(亿)" data-index="sgt">
                <template #cell="{ record }">{{ fmtNum(record.sgt) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </div>
        <a-empty v-else description="暂无数据" />
      </a-tab-pane>

      <!-- 4. 陆股通十大 -->
      <a-tab-pane key="hsgt-top10" title="陆股通十大">
        <a-space style="margin-bottom: 12px">
          <span>交易日：</span>
          <a-date-picker v-model="hsgtDate" value-format="YYYY-MM-DD" @change="loadHsgtTop10" />
        </a-space>
        <div v-if="hsgtTop10.length">
          <a-table :data="hsgtTop10" :pagination="{ pageSize: 20 }" size="small">
            <template #columns>
              <a-table-column title="代码" data-index="symbol" :width="110" />
              <a-table-column title="交易日" data-index="trade_date" :width="120" />
              <a-table-column title="市场" data-index="gtype" :width="90" />
              <a-table-column title="排名" data-index="rank" :width="70" />
              <a-table-column title="买入(万)" data-index="buy_amount">
                <template #cell="{ record }">{{ fmtNum(record.buy_amount) }}</template>
              </a-table-column>
              <a-table-column title="卖出(万)" data-index="sell_amount">
                <template #cell="{ record }">{{ fmtNum(record.sell_amount) }}</template>
              </a-table-column>
              <a-table-column title="净买入(万)" data-index="net_amount">
                <template #cell="{ record }">
                  <span :style="{ color: (record.net_amount ?? 0) >= 0 ? '#ef232a' : '#14b143' }">
                    {{ fmtNum(record.net_amount) }}
                  </span>
                </template>
              </a-table-column>
            </template>
          </a-table>
        </div>
        <a-empty v-else description="暂无数据" />
      </a-tab-pane>

      <!-- 5. 两融余额 -->
      <a-tab-pane key="margin" title="两融余额">
        <div v-if="margin.length">
          <div ref="marginEl" style="width: 100%; height: 380px"></div>
        </div>
        <a-empty v-else description="暂无数据" />
      </a-tab-pane>

      <!-- 6. IPO新股 -->
      <a-tab-pane key="new-share" title="IPO新股">
        <div v-if="newShare.length">
          <a-table :data="newShare" :pagination="{ pageSize: 20 }" size="small">
            <template #columns>
              <a-table-column title="代码" data-index="symbol" :width="110" />
              <a-table-column title="名称" data-index="name" :ellipsis="true" />
              <a-table-column title="发行价" data-index="price" :width="100">
                <template #cell="{ record }">{{ fmtNum(record.price) }}</template>
              </a-table-column>
              <a-table-column title="发行总量(万股)" data-index="total_amount" :width="140">
                <template #cell="{ record }">{{ fmtNum(record.total_amount) }}</template>
              </a-table-column>
              <a-table-column title="网上发行(万股)" data-index="online_amount" :width="140">
                <template #cell="{ record }">{{ fmtNum(record.online_amount) }}</template>
              </a-table-column>
              <a-table-column title="发行日期" data-index="issue_date" :width="120" />
              <a-table-column title="上市日期" data-index="list_date" :width="120" />
            </template>
          </a-table>
        </div>
        <a-empty v-else description="暂无数据" />
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import { fmtDateLocal as fmt } from '../utils/date.js'

const indexOptions = [
  { code: '000001.SH', label: '上证指数' },
  { code: '000300.SH', label: '沪深300' },
  { code: '000905.SH', label: '中证500' },
  { code: '399001.SZ', label: '深证成指' },
  { code: '399006.SZ', label: '创业板指' },
  { code: '000688.SH', label: '科创50' },
]
const indexCode = ref('000001.SH')
const today = new Date()
const lastYear = new Date(today)
lastYear.setFullYear(today.getFullYear() - 1)
const indexRange = ref([fmt(lastYear), fmt(today)])

const globalLoading = ref(false)
const loaded = {}

const indexBars = ref([])
const toplist = ref([])
const toplistDate = ref('')
const toplistExpanded = ref([])
const topinstCache = ref({})
const topinstLoading = ref({})
const hsgtFlow = ref([])
const hsgtTop10 = ref([])
const hsgtDate = ref('')
const margin = ref([])
const newShare = ref([])

const indexEl = ref(null)
const hsgtFlowEl = ref(null)
const marginEl = ref(null)
let indexChart = null
let hsgtFlowChart = null
let marginChart = null

function fmtNum(v) {
  if (v == null) return '--'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
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

function onTabChange(key) {
  nextTick(() => {
    indexChart && indexChart.resize()
    hsgtFlowChart && hsgtFlowChart.resize()
    marginChart && marginChart.resize()
  })
  if (key && !loaded[key]) loadTab(key)
}

async function loadTab(key) {
  if (loaded[key]) return
  loaded[key] = true
  try {
    if (key === 'index') await loadIndex()
    else if (key === 'toplist') await loadToplist()
    else if (key === 'hsgt-flow') {
      hsgtFlow.value = await getJSON('/api/hsgt-flow?limit=120')
      await nextTick()
      renderHsgtFlowChart()
    } else if (key === 'hsgt-top10') await loadHsgtTop10()
    else if (key === 'margin') {
      margin.value = await getJSON('/api/margin?limit=120')
      await nextTick()
      renderMarginChart()
    } else if (key === 'new-share') {
      newShare.value = await getJSON('/api/new-share?limit=20')
    }
  } catch (e) {
    loaded[key] = false
    Message.error(`加载失败：${e.message}`)
  }
}

async function loadIndex() {
  if (!indexRange.value || indexRange.value.length !== 2) return
  const [from, to] = indexRange.value
  indexBars.value = await getJSON(
    `/api/index-daily?ts_code=${indexCode.value}&from=${from}&to=${to}`
  )
  await nextTick()
  renderIndexChart()
}

async function loadToplist() {
  const url = toplistDate.value ? `/api/top-list?date=${toplistDate.value}` : '/api/top-list'
  toplist.value = await getJSON(url)
  if (toplist.value.length && !toplistDate.value) {
    toplistDate.value = toplist.value[0].trade_date
  }
}

// 龙虎榜行展开：懒加载该股机构明细（top_inst），缓存按 symbol+日期 key
const topinstKey = (sym) => `${sym}|${toplistDate.value || ''}`
async function onToplistExpand(record) {
  const sym = record.symbol
  const key = topinstKey(sym)
  if (topinstCache.value[key] || topinstLoading.value[key]) return
  topinstLoading.value[key] = true
  try {
    const dateParam = toplistDate.value ? `&date=${toplistDate.value}` : ''
    topinstCache.value[key] = await getJSON(`/api/top-inst?symbol=${sym}&limit=50${dateParam}`)
  } catch (e) {
    Message.error(`机构明细加载失败：${e.message}`)
  } finally {
    topinstLoading.value[key] = false
  }
}

async function loadHsgtTop10() {
  const url = hsgtDate.value ? `/api/hsgt-top10?date=${hsgtDate.value}` : '/api/hsgt-top10'
  hsgtTop10.value = await getJSON(url)
  if (hsgtTop10.value.length && !hsgtDate.value) {
    hsgtDate.value = hsgtTop10.value[0].trade_date
  }
}

function renderIndexChart() {
  if (!indexEl.value || !indexBars.value.length) return
  indexChart && indexChart.dispose()
  indexChart = echarts.init(indexEl.value)
  const rows = [...indexBars.value].reverse()
  const dates = rows.map((r) => r.date)
  const candles = rows.map((r) => [r.open, r.close, r.low, r.high])
  const vols = rows.map((r) => r.vol)
  indexChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', '成交量'] },
    grid: [
      { left: '8%', right: '8%', top: '8%', height: '56%' },
      { left: '8%', right: '8%', top: '70%', height: '18%' },
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
      {
        name: '成交量', type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: (p) => {
          const c = candles[p.dataIndex]
          return c && c[1] >= c[0] ? '#ef232a' : '#14b143'
        } },
      },
    ],
  }, true)
}

function renderHsgtFlowChart() {
  if (!hsgtFlowEl.value || !hsgtFlow.value.length) return
  hsgtFlowChart && hsgtFlowChart.dispose()
  hsgtFlowChart = echarts.init(hsgtFlowEl.value)
  const rows = [...hsgtFlow.value].reverse()
  const dates = rows.map((r) => r.trade_date)
  const pick = (k) => rows.map((r) => (r[k] != null ? +Number(r[k]).toFixed(2) : '-'))
  hsgtFlowChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['北向资金(亿)', '南向资金(亿)'] },
    grid: { left: '8%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '北向(亿)' },
      { type: 'value', name: '南向(亿)' },
    ],
    series: [
      {
        name: '北向资金(亿)', type: 'line', data: pick('north_money'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, itemStyle: { color: '#ef232a' },
      },
      {
        name: '南向资金(亿)', type: 'line', data: pick('south_money'), smooth: true, showSymbol: false,
        lineStyle: { width: 1.5 }, yAxisIndex: 1, itemStyle: { color: '#165dff' },
      },
    ],
  })
}

function renderMarginChart() {
  if (!marginEl.value || !margin.value.length) return
  marginChart && marginChart.dispose()
  marginChart = echarts.init(marginEl.value)
  const rows = [...margin.value].reverse()
  const ids = [...new Set(rows.map((r) => r.exchange_id))]
  const dates = [...new Set(rows.map((r) => r.trade_date))].sort()
  const series = ids.map((id, i) => ({
    name: `${id}(亿)`,
    type: 'line',
    data: dates.map((d) => {
      const r = rows.find((x) => x.trade_date === d && x.exchange_id === id)
      return r && r.rzye != null ? +Number(r.rzye).toFixed(2) : '-'
    }),
    smooth: true,
    showSymbol: false,
    lineStyle: { width: 1.5 },
  }))
  marginChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: series.map((s) => s.name) },
    grid: { left: '8%', right: '8%', top: '12%', bottom: '12%' },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, fontSize: 10 } },
    yAxis: { type: 'value', name: '亿元' },
    series,
  })
}

function onResize() {
  indexChart && indexChart.resize()
  hsgtFlowChart && hsgtFlowChart.resize()
  marginChart && marginChart.resize()
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  loadTab('index')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  indexChart && indexChart.dispose()
  hsgtFlowChart && hsgtFlowChart.dispose()
  marginChart && marginChart.dispose()
})
</script>
