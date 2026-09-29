<template>
  <a-card :loading="loading">
    <template #title>
      <a-space>
        <a-link @click="$router.push('/blog')">← 返回</a-link>
        <span>{{ post.title }}</span>
      </a-space>
    </template>
    <template #extra>
      <a-button v-if="canManage" @click="$router.push(`/blog/edit/${post.id}`)">编辑</a-button>
    </template>
    <a-space style="margin-bottom: 12px">
      <a-tag v-if="post.category">{{ post.category }}</a-tag>
      <a-tag v-for="t in post.tags" :key="t" color="arcoblue">{{ t }}</a-tag>
      <span style="color: #86909c; font-size: 12px">{{ (post.published_at || '').slice(0, 10) }}</span>
    </a-space>
    <a-image v-if="post.cover_file_id" :src="`/api/files/${post.cover_file_id}`" width="100%" style="margin-bottom: 16px; border-radius: 8px" />
    <div class="md-body" v-html="html" />
  </a-card>
</template>

<script setup>
import { getJSON } from '../../../platform/utils/api.js'
import { hasPerm } from '../../../platform/utils/auth.js'
import { marked } from 'marked'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'

const route = useRoute()
const post = ref({})
const loading = ref(true)
const canManage = hasPerm('blog:manage')
const html = computed(() => marked.parse(post.value.content_md || ''))

onMounted(async () => {
  try {
    post.value = await getJSON(`/api/blog/posts/${route.params.slug}`)
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.md-body { line-height: 1.8; font-size: 15px; }
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3) { margin: 1.2em 0 0.6em; }
.md-body :deep(pre) { background: #f2f3f5; padding: 12px; border-radius: 8px; overflow: auto; }
.md-body :deep(code) { font-family: ui-monospace, monospace; font-size: 13px; }
.md-body :deep(img) { max-width: 100%; border-radius: 8px; }
.md-body :deep(blockquote) { border-left: 3px solid #d3a24a; padding-left: 12px; color: #666; margin: 1em 0; }
.md-body :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid #e5e6eb; padding: 8px 12px; }
</style>
