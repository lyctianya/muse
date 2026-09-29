<template>
  <a-card title="周文件下载">
    <a-alert style="margin-bottom: 16px">
      每周一 06:10 自动导出上周三市场日线（Parquet），发布到 GitHub Releases；
      用 <a-typography-text code>merger/merger.py</a-typography-text> 可幂等合并到本地库。
    </a-alert>
    <a-table :columns="columns" :data="rows" :loading="loading" :pagination="false" row-key="week">
      <template #empty>
        <a-empty description="暂无周文件，待首次周导出任务运行后展示" />
      </template>
      <template #action="{ record }">
        <a-space wrap>
          <a-link v-for="f in record._files" :key="f.file" :href="f.url" target="_blank">
            {{ f.file }}
          </a-link>
        </a-space>
      </template>
    </a-table>
    <div v-if="note" style="margin-top: 12px; color: #86909c; font-size: 12px">{{ note }}</div>
  </a-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'

const rows = ref([])
const loading = ref(false)
const note = ref('')
const columns = [
  { title: '周', dataIndex: 'week', width: 140 },
  { title: '覆盖区间', dataIndex: 'range', width: 260 },
  { title: '文件', dataIndex: 'files' },
  { title: '操作', slotName: 'action', width: 120 },
]

async function load() {
  loading.value = true
  try {
    const res = await fetch('/api/weeks')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    note.value = data.note || ''
    rows.value = (data.weeks || []).map((w) => ({
      week: w.week,
      range: w.start && w.end ? `${w.start} ~ ${w.end}` : (w.published_at || '').slice(0, 10),
      files: Object.values(w.files || {}).map((f) => f.file).join('、'),
      _files: Object.values(w.files || {}).filter((f) => f.file.endsWith('.parquet')),
      _raw: w,
    }))
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
