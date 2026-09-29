<template>
  <a-card :loading="loading">
    <template #title>
      <a-space>
        <a-link @click="$router.push('/gallery')">← 返回</a-link>
        <span>{{ album.title }}</span>
        <a-tag>{{ (album.photos || []).length }} 张</a-tag>
      </a-space>
    </template>
    <template #extra>
      <a-upload v-if="canUpload" :custom-request="doUpload" :show-file-list="false" multiple accept="image/*">
        <template #upload-button>
          <a-button type="primary" :loading="uploading">上传照片</a-button>
        </template>
      </a-upload>
    </template>
    <div v-if="album.description" style="color: #86909c; margin-bottom: 16px">{{ album.description }}</div>
    <a-row :gutter="12">
      <a-col :span="6" v-for="(p, i) in album.photos" :key="p.id" style="margin-bottom: 12px">
        <div class="photo" @click="preview(i)">
          <a-image :src="p.url" height="200" fit="cover" :preview="false" width="100%" />
          <div class="photo-bar">
            <span class="caption">{{ p.caption || '' }}</span>
            <a-link v-if="canUpload" status="danger" @click.stop="remove(p)">删除</a-link>
          </div>
        </div>
      </a-col>
    </a-row>
    <a-empty v-if="!loading && !(album.photos || []).length" description="相册是空的，上传些照片吧" />
    <a-image-preview-group v-model:visible="previewVisible" :src-list="srcList" :default-current="previewIndex" />
  </a-card>
</template>

<script setup>
import { apiFetch, getJSON, postJSON, del } from '../../../platform/utils/api.js'
import { hasPerm } from '../../../platform/utils/auth.js'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'

const route = useRoute()
const album = ref({ photos: [] })
const loading = ref(true)
const uploading = ref(false)
const previewVisible = ref(false)
const previewIndex = ref(0)
const canUpload = hasPerm('gallery:upload')
const srcList = computed(() => (album.value.photos || []).map((p) => p.url))

async function load() {
  loading.value = true
  try {
    album.value = await getJSON(`/api/gallery/albums/${route.params.id}`)
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function doUpload({ fileItem, onSuccess, onError }) {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', fileItem.file)
  try {
    const meta = await (await apiFetch('/api/files/upload', { method: 'POST', body: fd })).json()
    await postJSON(`/api/gallery/albums/${route.params.id}/photos`, [{ file_id: meta.id }])
    Message.success(`已上传：${fileItem.name}`)
    onSuccess()
    load()
  } catch (e) {
    Message.error(`上传失败：${e.message}`)
    onError(e)
  } finally {
    uploading.value = false
  }
}

function preview(i) {
  previewIndex.value = i
  previewVisible.value = true
}

function remove(p) {
  Modal.confirm({
    title: '删除照片', content: '确定删除这张照片吗？',
    okText: '删除', okButtonProps: { status: 'danger' },
    onOk: async () => {
      try { await del(`/api/gallery/photos/${p.id}`); Message.success('已删除'); load() }
      catch (e) { Message.error(`删除失败：${e.message}`) }
    },
  })
}

onMounted(load)
</script>

<style scoped>
.photo { border-radius: 8px; overflow: hidden; cursor: zoom-in; border: 1px solid #e5e6eb; }
.photo-bar { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: #fff; }
.caption { font-size: 12px; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
