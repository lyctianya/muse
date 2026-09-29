<template>
  <a-card title="相册">
    <template #extra>
      <a-button v-if="canUpload" type="primary" @click="showCreate = true">新建相册</a-button>
    </template>
    <a-row :gutter="16" v-if="!loading">
      <a-col :span="6" v-for="a in albums" :key="a.id" style="margin-bottom: 16px">
        <a-card hoverable @click="$router.push(`/gallery/${a.id}`)" style="cursor: pointer">
          <template #cover>
            <a-image v-if="a.cover_file_id" :src="`/api/files/${a.cover_file_id}`" height="180" fit="cover" :preview="false" />
            <div v-else style="height: 180px; background: #f2f3f5; display: flex; align-items: center; justify-content: center; color: #86909c">空相册</div>
          </template>
          <a-card-meta :title="a.title" :description="`${a.photo_count} 张 · ${(a.created_at || '').slice(0, 10)}`" />
          <template #actions v-if="canUpload">
            <a-link status="danger" @click.stop="remove(a)">删除</a-link>
          </template>
        </a-card>
      </a-col>
    </a-row>
    <a-empty v-if="!loading && !albums.length" description="还没有相册" />
    <a-modal v-model:visible="showCreate" title="新建相册" @ok="create" :ok-loading="creating">
      <a-form :model="form" layout="vertical">
        <a-form-item label="标题"><a-input v-model="form.title" placeholder="相册标题" /></a-form-item>
        <a-form-item label="描述"><a-textarea v-model="form.description" :rows="3" /></a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup>
import { getJSON, postJSON, del } from '../../../platform/utils/api.js'
import { hasPerm } from '../../../platform/utils/auth.js'
import { ref, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'

const albums = ref([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const form = ref({ title: '', description: '' })
const canUpload = hasPerm('gallery:upload')

async function load() {
  loading.value = true
  try {
    const data = await getJSON('/api/gallery/albums')
    albums.value = data.items || []
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function create() {
  if (!form.value.title.trim()) { Message.warning('请填写标题'); return }
  creating.value = true
  try {
    await postJSON('/api/gallery/albums', form.value)
    Message.success('已创建')
    showCreate.value = false
    form.value = { title: '', description: '' }
    load()
  } catch (e) {
    Message.error(`创建失败：${e.message}`)
  } finally {
    creating.value = false
  }
}

function remove(a) {
  Modal.confirm({
    title: '删除相册', content: `确定删除「${a.title}」及其中 ${a.photo_count} 张照片吗？`,
    okText: '删除', okButtonProps: { status: 'danger' },
    onOk: async () => {
      try { await del(`/api/gallery/albums/${a.id}`); Message.success('已删除'); load() }
      catch (e) { Message.error(`删除失败：${e.message}`) }
    },
  })
}

onMounted(load)
</script>
