<template>
  <a-card title="文件管理">
    <a-alert style="margin-bottom: 16px">
      共享文件存储：博客配图、相册原图、游戏资源都走这里。单文件上限 200MB。
    </a-alert>
    <a-upload
      v-if="canUpload"
      :custom-request="doUpload"
      :show-file-list="false"
      multiple
      draggable
      style="margin-bottom: 16px"
    />
    <a-table :columns="columns" :data="rows" :loading="loading" :pagination="false" row-key="id">
      <template #empty>
        <a-empty description="还没有文件，上传第一个吧" />
      </template>
      <template #size="{ record }">
        {{ fmtSize(record.size_bytes) }}
      </template>
      <template #created="{ record }">
        {{ (record.created_at || '').slice(0, 19).replace('T', ' ') }}
      </template>
      <template #action="{ record }">
        <a-space>
          <a-link :href="`/api/files/${record.id}`" target="_blank">下载</a-link>
          <a-link v-if="record.mine || canManage" status="danger" @click="remove(record)">删除</a-link>
        </a-space>
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { apiFetch, getJSON, del } from '../../../platform/utils/api.js'
import { hasPerm } from '../../../platform/utils/auth.js'
import { ref, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'

const rows = ref([])
const loading = ref(false)
const canUpload = hasPerm('files:upload')
const canManage = hasPerm('files:manage')
const columns = [
  { title: '文件名', dataIndex: 'filename' },
  { title: '大小', dataIndex: 'size_bytes', slotName: 'size', width: 110 },
  { title: '类型', dataIndex: 'mime', width: 200 },
  { title: '上传时间', dataIndex: 'created_at', slotName: 'created', width: 180 },
  { title: '操作', slotName: 'action', width: 140 },
]

function fmtSize(n) {
  if (!n) return '-'
  const u = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (n >= 1024 && i < 3) { n /= 1024; i++ }
  return `${n.toFixed(1)} ${u[i]}`
}

async function load() {
  loading.value = true
  try {
    const data = await getJSON('/api/files/')
    rows.value = data.items || []
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function doUpload({ fileItem, onSuccess, onError }) {
  const fd = new FormData()
  fd.append('file', fileItem.file)
  try {
    await apiFetch('/api/files/upload', { method: 'POST', body: fd })
    Message.success(`已上传：${fileItem.name}`)
    onSuccess()
    load()
  } catch (e) {
    Message.error(`上传失败：${e.message}`)
    onError(e)
  }
}

function remove(record) {
  Modal.confirm({
    title: '删除文件',
    content: `确定删除「${record.filename}」吗？`,
    okText: '删除',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      try {
        await del(`/api/files/${record.id}`)
        Message.success('已删除')
        load()
      } catch (e) {
        Message.error(`删除失败：${e.message}`)
      }
    },
  })
}

onMounted(load)
</script>
