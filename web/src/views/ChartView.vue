<template>
  <a-card>
    <template #title>
      <a-space>
        <a-button shape="circle" @click="$router.back()"><icon-left /></a-button>
        <span>{{ title }}</span>
        <a-tag>{{ marketLabel }}</a-tag>
      </a-space>
    </template>
    <template #extra>
      <a-range-picker
        v-model="range"
        value-format="YYYY-MM-DD"
        style="width: 280px"
        @change="loadBars"
      />
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

const props = defineProps({ market: String, symbol: String })
const route = useRoute()
const stockName = computed(() => route.query.name || '')

const LABELS = { cn: 'A股', hk: '港股', us: '美股' }
const marketLabel = computed(() => LABELS[props.market] || props.market)
const title = computed(() => `${stockName.value} ${props.symbol}`.trim())

const chartEl = ref(null)
const loading = ref(false)
let chart = null

// 默认近一年
const today = new Date()
const fmt = (d) => d.toISOString().slice(0, 10)
const lastYear = new Date(today)
lastYear.setFullYear(today.getFullYear() - 1)
const range = ref([fmt(lastYear), fmt(today)])

function ma(data, n) {
  // 简单移动平均（收盘价）
  const out = []
  for (let i = 0; i < data.length; i++) {
    if (i < n - 1) { out.push('-'); continue }
    let sum = 0
    for (let j = 0; j < n; j++) sum += data[i - j].close
    out.push(+(sum / n).toFixed(2))
  }
  return out
}

function renderOption(bars) {
  const dates = bars.map((b) => b.date)
  const candles = bars.map((b) => [b.open, b.close, b.low, b.high])
  const volumes = bars.map((b, i) => [
    i,
    b.volume,
    b.close >= b.open ? 1 : -1, // 涨红跌绿
  ])
  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', 'MA5', 'MA10', '成交量'] },
    grid: [
      { left: '8%', right: '8%', top: '8%', height: '58%' },
      { left: '8%', right: '8%', top: '72%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, axisLabel: { hideOverlap: true } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
      { type: 'slider', xAxisIndex: [0, 1], top: '92%' },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: candles,
        itemStyle: {
          color: '#ef232a', color0: '#14b143',
          borderColor: '#ef232a', borderColor0: '#14b143',
        },
      },
      { name: 'MA5', type: 'line', data: ma(bars, 5), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: 'MA10', type: 'line', data: ma(bars, 10), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes,
        itemStyle: {
          color: (p) => (p.value[2] > 0 ? '#ef232a' : '#14b143'),
        },
      },
    ],
  }
}

async function loadBars() {
  if (!range.value || range.value.length !== 2) return
  loading.value = true
  try {
    const params = new URLSearchParams({
      market: props.market,
      symbol: props.symbol,
      from: range.value[0],
      to: range.value[1],
    })
    const res = await fetch(`/api/bars?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const bars = await res.json()
    if (!bars.length) {
      Message.info('该区间暂无行情数据')
      chart && chart.clear()
      return
    }
    chart.setOption(renderOption(bars), true)
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
