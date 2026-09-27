<template>
  <a-card>
    <template #title>
      <a-space>
        <a-button shape="circle" @click="$router.back()"><icon-left /></a-button>
        <span>{{ title }}</span>
        <a-tag>{{ marketLabel }}</a-tag>
        <WatchStar :market="props.market" :symbol="props.symbol" />
      </a-space>
    </template>
    <template #extra>
      <a-space>
        <a-segmented v-model="indicator" :options="indicatorOptions" @change="loadBars" />
        <a-range-picker
          v-model="range"
          value-format="YYYY-MM-DD"
          style="width: 280px"
          @change="loadBars"
        />
      </a-space>
    </template>
    <a-spin :loading="loading" style="width: 100%">
      <div ref="chartEl" style="width: 100%; height: 560px"></div>
    </a-spin>
  </a-card>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconLeft } from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'
import WatchStar from '../components/WatchStar.vue'

const props = defineProps({ market: String, symbol: String })
const route = useRoute()
const stockName = computed(() => route.query.name || '')

const LABELS = { cn: 'A股', hk: '港股', us: '美股' }
const marketLabel = computed(() => LABELS[props.market] || props.market)
const title = computed(() => `${stockName.value} ${props.symbol}`.trim())

const chartEl = ref(null)
const loading = ref(false)
let chart = null

const indicatorOptions = [
  { label: 'MACD', value: 'macd' },
  { label: 'KDJ', value: 'kdj' },
  { label: 'BOLL', value: 'boll' },
]
const indicator = ref('macd')

// 默认近一年
const today = new Date()
const fmt = (d) => d.toISOString().slice(0, 10)
const lastYear = new Date(today)
lastYear.setFullYear(today.getFullYear() - 1)
const range = ref([fmt(lastYear), fmt(today)])

function ma(data, n) {
  const out = []
  for (let i = 0; i < data.length; i++) {
    if (i < n - 1) { out.push('-'); continue }
    let sum = 0
    for (let j = 0; j < n; j++) sum += data[i - j].close
    out.push(+(sum / n).toFixed(2))
  }
  return out
}

// 把指标序列按日期对齐到 bars
function alignSeries(bars, tech, colIdx) {
  const m = new Map(tech.dates.map((d, i) => [d, tech.values[i][colIdx]]))
  return bars.map((b) => {
    const v = m.get(b.date)
    return v == null ? '-' : +Number(v).toFixed(3)
  })
}

function renderOption(bars, tech) {
  const dates = bars.map((b) => b.date)
  const candles = bars.map((b) => [b.open, b.close, b.low, b.high])
  const volumes = bars.map((b, i) => [i, b.volume, b.close >= b.open ? 1 : -1])

  const series = [
    {
      name: 'K线', type: 'candlestick', data: candles,
      itemStyle: {
        color: '#ef232a', color0: '#14b143',
        borderColor: '#ef232a', borderColor0: '#14b143',
      },
    },
    { name: 'MA5', type: 'line', data: ma(bars, 5), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
    { name: 'MA10', type: 'line', data: ma(bars, 10), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
  ]
  const legend = ['K线', 'MA5', 'MA10']

  // BOLL 叠加在主图
  if (indicator.value === 'boll' && tech) {
    const upper = alignSeries(bars, tech, 0)
    const mid = alignSeries(bars, tech, 1)
    const lower = alignSeries(bars, tech, 2)
    series.push(
      { name: 'BOLL上轨', type: 'line', data: upper, showSymbol: false, lineStyle: { width: 1, color: '#e74c3c' } },
      { name: 'BOLL中轨', type: 'line', data: mid, showSymbol: false, lineStyle: { width: 1, color: '#f1c40f' } },
      { name: 'BOLL下轨', type: 'line', data: lower, showSymbol: false, lineStyle: { width: 1, color: '#2ecc71' } },
    )
    legend.push('BOLL上轨', 'BOLL中轨', 'BOLL下轨')
  }

  // 副图：成交量 + 指标
  const subSeries = [
    {
      name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes,
      itemStyle: { color: (p) => (p.value[2] > 0 ? '#ef232a' : '#14b143') },
    },
  ]
  legend.push('成交量')

  if (tech && indicator.value === 'macd') {
    const dif = alignSeries(bars, tech, 0)
    const dea = alignSeries(bars, tech, 1)
    const hist = alignSeries(bars, tech, 2)
    subSeries.push(
      { name: 'DIF', type: 'line', data: dif, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 2, yAxisIndex: 2 },
      { name: 'DEA', type: 'line', data: dea, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 2, yAxisIndex: 2 },
      {
        name: 'MACD', type: 'bar', data: hist, xAxisIndex: 2, yAxisIndex: 2,
        itemStyle: { color: (p) => (p.value > 0 ? '#ef232a' : '#14b143') },
      },
    )
    legend.push('DIF', 'DEA', 'MACD')
  } else if (tech && indicator.value === 'kdj') {
    const k = alignSeries(bars, tech, 0)
    const d = alignSeries(bars, tech, 1)
    const j = alignSeries(bars, tech, 2)
    subSeries.push(
      { name: 'K', type: 'line', data: k, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 2, yAxisIndex: 2 },
      { name: 'D', type: 'line', data: d, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 2, yAxisIndex: 2 },
      { name: 'J', type: 'line', data: j, showSymbol: false, lineStyle: { width: 1 }, xAxisIndex: 2, yAxisIndex: 2 },
    )
    legend.push('K', 'D', 'J')
  }

  const grids = [
    { left: '8%', right: '8%', top: '8%', height: '50%' },
    { left: '8%', right: '8%', top: '63%', height: '14%' },
  ]
  const xAxes = [
    { type: 'category', data: dates, scale: true, axisLabel: { hideOverlap: true } },
    { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
  ]
  const yAxes = [
    { scale: true, splitArea: { show: true } },
    { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
  ]
  // 有 MACD/KDJ 时加第三个副图
  const showThird = tech && (indicator.value === 'macd' || indicator.value === 'kdj')
  if (showThird) {
    grids[0].height = '44%'
    grids[1].top = '57%'
    grids[1].height = '12%'
    grids.push({ left: '8%', right: '8%', top: '73%', height: '15%' })
    xAxes.push({ type: 'category', data: dates, gridIndex: 2, axisLabel: { show: false } })
    yAxes.push({ scale: true, gridIndex: 2, splitNumber: 2 })
  }

  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: legend },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2] },
      { type: 'slider', xAxisIndex: [0, 1, 2], top: '92%' },
    ],
    series: [...series, ...subSeries],
  }
}

async function loadBars() {
  if (!range.value || range.value.length !== 2) return
  loading.value = true
  try {
    const base = {
      market: props.market,
      symbol: props.symbol,
      from: range.value[0],
      to: range.value[1],
    }
    const [barsRes, techRes] = await Promise.all([
      fetch(`/api/bars?${new URLSearchParams(base)}`),
      fetch(`/api/tech?${new URLSearchParams({ ...base, indicator: indicator.value })}`),
    ])
    if (!barsRes.ok) throw new Error(`HTTP ${barsRes.status}`)
    if (!techRes.ok) throw new Error(`HTTP ${techRes.status}`)
    const bars = await barsRes.json()
    const tech = await techRes.json()
    if (!bars.length) {
      Message.info('该区间暂无行情数据')
      chart && chart.clear()
      return
    }
    chart.setOption(renderOption(bars, tech), true)
  } catch (e) {
    Message.error(`加载行情失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function onResize() { chart && chart.resize() }

onMounted(() => {
  chart = echarts.init(chartEl.value)
  window.addEventListener('resize', onResize)
  loadBars()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
})
</script>
