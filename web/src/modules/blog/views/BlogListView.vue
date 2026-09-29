<template>
  <a-card title="博客">
    <template #extra>
      <a-space>
        <a-select v-model="tagFilter" placeholder="标签筛选" allow-clear style="width: 160px" @change="load">
          <a-option v-for="t in tags" :key="t.name" :value="t.name">{{ t.name }} ({{ t.count }})</a-option>
        </a-select>
        <a-button v-if="canManage" type="primary" @click="$router.push('/blog/new')">写文章</a-button>
      </a-space>
    </template>
    <a-tabs v-if="canManage" v-model:active-key="tab" @change="load" style="margin-bottom: 8px">
      <a-tab-pane key="published" title="已发布" />
      <a-tab-pane key="draft" title="草稿箱" />
    </a-tabs>
    <a-list :loading="loading" :data="posts" :bordered="false">
      <template #empty><a-empty description="还没有文章" /></template>
      <a-list-item v-for="p in posts" :key="p.id" @click="$router.push(`/blog/${p.slug}`)" style="cursor: pointer">
        <a-list-item-meta>
          <template #avatar>
            <a-image v-if="p.cover_file_id" :src="`/api/files/${p.cover_file_id}`" width="120" height="80" fit="cover" :preview="false" />
            <div v-else style="width: 120px; height: 80px; background: #f2f3f5; border-radius: 6px" />
          </template>
          <template #title>
            <a-space>
              <span style="font-size: 16px; font-weight: 600">{{ p.title }}</span>
              <a-tag v-if="p.status === 'draft'" color="orange">草稿</a-tag>
            </a-space>
          </template>
          <template #description>
            <div style="margin: 4px 0">{{ p.excerpt }}</div>
            <a-space>
              <a-tag v-if="p.category" size="small">{{ p.category }}</a-tag>
              <a-tag v-for="t in p.tags" :key="t" size="small" color="arcoblue">{{ t }}</a-tag>
              <span style="color: #86909c; font-size: 12px">{{ (p.published_at || p.created_at || '').slice(0, 10) }}</span>
            </a-space>
          </template>
        </a-list-item-meta>
        <template #actions v-if="canManage">
          <a-link @click.stop="$router.push(`/blog/edit/${p.id}`)">编辑</a-link>
          <a-link status="danger" @click.stop="remove(p)">删除</a-link>
        </template>
      </a-list-item>
    </a-list>
  </a-card>
</template>

<script setup>
import { getJSON, del } from '../../../platform/utils/api.js'
import { hasPerm } from '../../../platform/utils/auth.js'
import { ref, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'

const posts = ref([])
const tags = ref([])
const loading = ref(false)
const tab = ref('published')
const tagFilter = ref('')
const canManage = hasPerm('blog:manage')

async function load() {
  loading.value = true
  try {
    const q = new URLSearchParams({ status: tab.value })
    if (tagFilter.value) q.set('tag', tagFilter.value)
    const data = await getJSON(`/api/blog/posts?${q}`)
    posts.value = data.items || []
    const tg = await getJSON('/api/blog/tags')
    tags.value = tg.items || []
  } catch (e) {
    Message.error(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function remove(p) {
  Modal.confirm({
    title: '删除文章', content: `确定删除「${p.title}」吗？`,
    okText: '删除', okButtonProps: { status: 'danger' },
    onOk: async () => {
      try { await del(`/api/blog/posts/${p.id}`); Message.success('已删除'); load() }
      catch (e) { Message.error(`删除失败：${e.message}`) }
    },
  })
}

onMounted(load)
</script>
