<template>
  <a-empty v-if="!rows.length" description="暂无数据" />
  <a-table
    v-else
    :data="tableRows"
    :columns="columns"
    :pagination="{ pageSize: 10 }"
    size="small"
    :scroll="{ x: Math.max(800, columns.length * 140) }"
    row-key="report_date"
  />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  /** 优先展示的提取列：[{ key, title, format? }] */
  extras: { type: Array, default: () => [] },
})

function fmtCell(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + ' 亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + ' 万'
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const SKIP_DATA_KEYS = new Set(['ts_code', 'end_date', 'ann_date', 'symbol'])

const columns = computed(() => {
  if (!props.rows.length) return []
  const dataKeys = Object.keys(props.rows[0].data || {})
    .filter((k) => !SKIP_DATA_KEYS.has(k))
    .slice(0, 10)
  return [
    { title: '报告期', dataIndex: 'report_date', width: 120, fixed: 'left' },
    ...props.extras.map((e) => ({
      title: e.title,
      dataIndex: e.key,
      width: 140,
      render: ({ record }) => fmtCell(record[e.key]),
    })),
    ...dataKeys.map((k) => ({
      title: k,
      dataIndex: `_d_${k}`,
      width: 140,
      render: ({ record }) => fmtCell(record[`_d_${k}`]),
    })),
  ]
})

const tableRows = computed(() =>
  props.rows.map((r) => {
    const row = { report_date: r.report_date }
    for (const e of props.extras) row[e.key] = r[e.key]
    const data = r.data || {}
    for (const k of Object.keys(data)) {
      if (SKIP_DATA_KEYS.has(k)) continue
      row[`_d_${k}`] = data[k]
    }
    return row
  }),
)
</script>
