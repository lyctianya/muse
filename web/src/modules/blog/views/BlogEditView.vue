<template>
  <a-card :title="isNew ? '写文章' : '编辑文章'">
    <a-form :model="form" layout="vertical">
      <a-form-item label="标题">
        <a-input v-model="form.title" placeholder="文章标题" />
      </a-form-item>
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="分类">
            <a-input v-model="form.category" placeholder="如：技术、生活" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="标签（逗号分隔）">
            <a-input v-model="tagsText" placeholder="如：vue, 架构" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="封面图">
            <a-upload :custom-request="uploadCover" :show-file-list="false" :limit="1">
              <template #upload-button>
                <a-button size="small">{{ form.cover_file_id ? '已上传，点击更换' : '上传封面' }}</a-button>
              </template>
            </a-upload>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="正文（Markdown）">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-textarea v-model="form.content_md" :rows="22" placeholder="# 标题&#10;&#10;正文内容…" />
          </a-col>
          <a-col :span="12">
            <div class="md-preview" v-html="html" />
          </a-col>
        </a-row>
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button @click="save('draft')" :loading="saving">存草稿</a-button>
          <a-button type="primary" @click="save('published')" :loading="saving">发布</a-button>
          <a-button @click="$router.push('/blog')">取消</a-button>
        </a-space>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup>
import { apiFetch, getJSON, postJSON, putJSON } from '../../../platform/utils/api.js'
import { marked } from 'marked'
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'

const route = useRoute()
const router = useRouter()
const isNew = computed(() => route.name === 'blog-new')
const form = ref({ title: '', content_md: '', category: '', cover_file_id: null })
const tagsText = ref('')
const saving = ref(false)
const html = computed(() => marked.parse(form.value.content_md || ''))

async function uploadCover({ fileItem, onSuccess, onError }) {
  const fd = new FormData()
  fd.append('file', fileItem.file)
  try {
    const meta = await (await apiFetch('/api/files/upload', { method: 'POST', body: fd })).json()
    form.value.cover_file_id = meta.id
    Message.success('封面已上传')
    onSuccess()
  } catch (e) {
    Message.error(`上传失败：${e.message}`)
    onError(e)
  }
}

async function save(status) {
  if (!form.value.title.trim()) { Message.warning('请填写标题'); return }
  saving.value = true
  try {
    const body = {
      title: form.value.title.trim(),
      content_md: form.value.content_md,
      category: form.value.category.trim(),
      cover_file_id: form.value.cover_file_id,
      status,
      tags: tagsText.value.split(/[,，]/).map((t) => t.trim()).filter(Boolean),
    }
    if (isNew.value) {
      const r = await postJSON('/api/blog/posts', body)
      Message.success(status === 'published' ? '已发布' : '已存草稿')
      router.push(`/blog/${r.slug}`)
    } else {
      await putJSON(`/api/blog/posts/${route.params.id}`, body)
      Message.success('已保存')
      router.push('/blog')
    }
  } catch (e) {
    Message.error(`保存失败：${e.message}`)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!isNew.value) {
    try {
      // 用 id 查：先取 slug 再取详情较绕，直接按 id 查 posts（后端按 slug 查，这里用列表兜底）
      const data = await getJSON('/api/blog/posts?status=draft&limit=200')
      const p = (data.items || []).find((x) => x.id === route.params.id)
      if (p) {
        const full = await getJSON(`/api/blog/posts/${p.slug}`)
        form.value = { title: full.title, content_md: full.content_md, category: full.category || '', cover_file_id: full.cover_file_id }
        tagsText.value = (full.tags || []).join(', ')
      }
    } catch (e) { Message.error(`加载失败：${e.message}`) }
  }
})
</script>

<style scoped>
.md-preview { border: 1px solid #e5e6eb; border-radius: 6px; padding: 12px; min-height: 480px; max-height: 560px; overflow: auto; line-height: 1.8; font-size: 14px; background: #fff; }
.md-preview :deep(pre) { background: #f2f3f5; padding: 10px; border-radius: 6px; overflow: auto; }
.md-preview :deep(img) { max-width: 100%; }
</style>
