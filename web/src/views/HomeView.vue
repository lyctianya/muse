<template>
  <div>
    <!-- 市场概览卡片 -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col v-for="m in markets" :key="m.key" :span="8">
        <a-card :loading="loading" class="market-card">
          <template #title>
            <span class="section-title">{{ m.label }}</span>
          </template>
          <template #extra>
            <a-tag size="small" color="arcoblue">{{ overviews[m.key]?.trade_date || '--' }}</a-tag>
          </template>
          <div v-if="overviews[m.key]?.found">
            <a-statistic
              title="总成交额"
              :value="fmtAmount(overviews[m.key].amount)"
              style="margin-bottom: 12px"
            />
            <a-row :gutter="8">
              <a-col :span="8">
                <a-statistic title="上涨" :value="overviews[m.key].up" value-style="color: var(--rise)" />
              </a-col>
              <a-col :span="8">
                <a-statistic title="下跌" :value="overviews[m.key].down" value-style="color: var(--fall)" />
              </a-col>
              <a-col :span="8">
                <a-statistic title="平盘" :value="overviews[m.key].flat" />
              </a-col>
            </a-row>
            <div :data-market="m.key" style="width: 100%; height: 160px; margin-top: 8px"></div>
            <div class="muted" style="margin-top: 4px">
              上市 {{ overviews[m.key].listed }} 家 · 有行情 {{ overviews[m.key].total }} 家
            </div>
          </div>
          <a-empty v-else description="暂无数据" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 涨跌排行 -->
    <a-card style="margin-bottom: 16px">
      <template #title>
        <a-space>
          <span class="section-title">涨跌排行</span>
          <a-select v-model="rankMarket" style="width: 100px" @change="loadRank">
            <a-option value="cn">A股</a-option>
            <a-option value="hk">港股</a-option>
            <a-option value="us">美股</a-option>
          </a-select>
        </a-space>
      </template>
      <a-row :gutter="16">
        <a-col :span="12">
          <div class="rank-head rise">▲ 涨幅榜</div>
          <a-table :data="gainers" :pagination="false" size="small">
            <template #columns>
              <a-table-column title="代码" data-index="symbol" :width="90">
                <template #cell="{ record }">
                  <a-link @click="goChart(record)">{{ record.symbol }}</a-link>
                </template>
              </a-table-column>
              <a-table-column title="名称" data-index="name" :ellipsis="true" />
              <a-table-column title="最新价" data-index="close" :width="100">
                <template #cell="{ record }">{{ fmtNum(record.close) }}</template>
              </a-table-column>
              <a-table-column title="涨跌幅" data-index="pct_change" :width="110">
                <template #cell="{ record }">
                  <span class="pct-badge rise">+{{ record.pct_change.toFixed(2) }}%</span>
                </template>
              </a-table-column>
            </template>
          </a-table>
        </a-col>
        <a-col :span="12">
          <div class="rank-head fall">▼ 跌幅榜</div>
          <a-table :data="losers" :pagination="false" size="small">
            <template #columns>
              <a-table-column title="代码" data-index="symbol" :width="90">
                <template #cell="{ record }">
                  <a-link @click="goChart(record)">{{ record.symbol }}</a-link>
                </template>
              </a-table-column>
              <a-table-column title="名称" data-index="name" :ellipsis="true" />
              <a-table-column title="最新价" data-index="close" :width="100">
                <template #cell="{ record }">{{ fmtNum(record.close) }}</template>
              </a-table-column>
              <a-table-column title="涨跌幅" data-index="pct_change" :width="110">
                <template #cell="{ record }">
                  <span class="pct-badge fall">{{ record.pct_change.toFixed(2) }}%</span>
                </template>
              </a-table-column>
            </template>
          </a-table>
        </a-col>
      </a-row>
    </a-card>

    <!-- 行业分布 -->
    <a-card>
      <template #title><span class="section-title">行业分布（A股）</span></template>
      <template #extra>
        <span class="muted">需回填基本面数据后展示</span>
      </template>
      <div v-if="sectors.length" ref="sectorEl" style="width: 100%; height: 380px"></div>
      <a-empty v-else description="暂无行业数据（基本面回填后自动展示）" />
    </a-card>
  </div>
</template>

<style scoped>
.rank-head {
  font-weight: 700; font-size: 14px; margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.rank-head.rise { color: var(--rise); }
.rank-head.fall { color: var(--fall); }
</style>

<script setup>
import { getJSON } from '../utils/api.js'
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { echarts, initChart } from '../utils/echarts-theme.js'

const router = useRouter()
const markets = [
  { key: 'cn', label: 'A股' },
  { key: 'hk', label: '港股' },
  { key: 'us', label: '美股' },
]
const overviews = ref({})
const gainers = ref([])
const losers = ref([])
const sectors = ref([])
const loading = ref(false)
const rankMarket = ref('cn')
const pieCharts = []
let sectorChart = null

function fmtNum(v) {
  if (v == null) return '--'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function fmtAmount(v) {
  if (v == null) return '--'
  if (v >= 1e12) return (v / 1e12).toFixed(2) + ' 万亿'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  return fmtNum(v)
}

function goChart(record) {
  router.push({
    path: `/chart/${rankMarket.value}/${record.symbol}`,
    query: { name: record.name },
  })
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function renderPies() {
  pieCharts.forEach((c) => c.dispose())
  pieCharts.length = 0
  const rise = cssVar('--rise') || '#e5484d'
  const fall = cssVar('--fall') || '#18a058'
  const flat = cssVar('--flat') || '#86909c'
  document.querySelectorAll('[data-market]').forEach((el) => {
    const key = el.getAttribute('data-market')
    const o = overviews.value[key]
    if (!o || !o.found) return
    const c = initChart(el)
    c.setOption({
      animation: false,
      tooltip: { trigger: 'item', formatter: '{b}: {c} 家 ({d}%)' },
      series: [{
        type: 'pie', radius: ['45%', '70%'],
        label: { show: false },
        data: [
          { value: o.up, name: '上涨', itemStyle: { color: rise } },
          { value: o.flat, name: '平盘', itemStyle: { color: flat } },
          { value: o.down, name: '下跌', itemStyle: { color: fall } },
        ],
      }],
    })
    pieCharts.push(c)
  })
}

function renderSectors() {
  if (!sectors.value.length || !sectorEl.value) return
  sectorChart && sectorChart.dispose()
  sectorChart = initChart(sectorEl.value)
  const top = sectors.value.slice(0, 20)
  sectorChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    grid: { left: '12%', right: '6%', top: '6%', bottom: '6%' },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: top.map((s) => s.industry).reverse(),
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: top.map((s) => s.count).reverse(),
      itemStyle: { color: '#165dff' },
      label: { show: true, position: 'right', fontSize: 10 },
    }],
  })
}
const sectorEl = ref(null)

function onResize() {
  pieCharts.forEach((c) => c.resize())
  sectorChart && sectorChart.resize()
}

async function loadRank() {
  try {
    const [g, l] = await Promise.all([
      getJSON(`/api/market/top?market=${rankMarket.value}&type=gainers&limit=10`),
      getJSON(`/api/market/top?market=${rankMarket.value}&type=losers&limit=10`),
    ])
    gainers.value = g
    losers.value = l
  } catch (e) {
    Message.error(`加载排行失败：${e.message}`)
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [cn, hk, us, sec] = await Promise.all([
      getJSON('/api/market/overview?market=cn'),
      getJSON('/api/market/overview?market=hk'),
      getJSON('/api/market/overview?market=us'),
      getJSON('/api/market/sectors?market=cn'),
    ])
    overviews.value = { cn, hk, us }
    sectors.value = sec
    await nextTick()
    renderPies()
    renderSectors()
    loadRank()
  } catch (e) {
    Message.error(`加载概览失败：${e.message}`)
  } finally {
    loading.value = false
  }
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  pieCharts.forEach((c) => c.dispose())
  sectorChart && sectorChart.dispose()
})
</script>
