<template>
  <a-card title="股票搜索">
    <a-space style="margin-bottom: 16px">
      <a-select v-model="market" style="width: 140px" placeholder="市场">
        <a-option value="">全部市场</a-option>
        <a-option value="cn">A股</a-option>
        <a-option value="hk">港股</a-option>
        <a-option value="us">美股</a-option>
      </a-select>
      <a-input-search
        v-model="q"
        placeholder="代码或名称，如 600519 / 茅台 / AAPL"
        search-button
        style="width: 360px"
        @search="doSearch"
        @press-enter="doSearch"
      />
    </a-space>

    <a-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :pagination="{ pageSize: 20, showTotal: true }"
      row-key="key"
      @row-click="goChart"
    >
      <template #market="{ record }">
        <a-tag :color="marketColor(record.market)">{{ marketLabel(record.market) }}</a-tag>
      </template>
      <template #action="{ record }">
        <a-button
          v-if="record.market === 'cn'"
          type="text"
          size="small"
          @click.stop="goCompany(record)"
        >
          基本面
        </a-button>
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { getJSON } from '../utils/api.js'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'

const router = useRouter()
const market = ref('')
const q = ref('')
const rows = ref([])
const loading = ref(false)

const columns = [
  { title: '市场', slotName: 'market', width: 100 },
  { title: '代码', dataIndex: 'symbol', width: 140 },
  { title: '名称', dataIndex: 'name', ellipsis: true },
  { title: '币种', dataIndex: 'currency', width: 100 },
  { title: '操作', slotName: 'action', width: 120 },
]

const LABELS = { cn: 'A股', hk: '港股', us: '美股' }
const COLORS = { cn: 'red', hk: 'blue', us: 'green' }
const marketLabel = (m) => LABELS[m] || m
const marketColor = (m) => COLORS[m] || 'gray'

async function doSearch() {
  loading.value = true
  try {
    const params = new URLSearchParams({ q: q.value, limit: '200' })
    if (market.value) params.set('market', market.value)
    const data = await getJSON(`/api/symbols?${params}`)
    rows.value = data.map((r) => ({ ...r, key: `${r.market}:${r.symbol}` }))
    if (!data.length) Message.info('没有找到匹配的股票')
  } catch (e) {
    Message.error(`搜索失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function goChart(record) {
  router.push({
    name: 'chart',
    params: { market: record.market, symbol: record.symbol },
    query: { name: record.name },
  })
}

function goCompany(record) {
  router.push({
    name: 'company',
    params: { symbol: record.symbol },
    query: { name: record.name },
  })
}

// 进页面自动搜一次（空关键字 = 浏览前 200 只）
doSearch()
</script>
