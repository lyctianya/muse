<template>
  <a-card :title="isNew ? '写文章' : '编辑文章'">
    <a-form :model="form" layout="vertical">
      <a-form-item label="标题">
        <a-input v-model="form.title" placeholder="文章标题" size="large" />
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
      <a-form-item label="正文">
        <div class="editor-wrap">
          <div v-if="editor" class="toolbar">
            <a-button-group size="small">
              <a-button @click="cmd('toggleBold')" :type="isActive('bold') ? 'primary' : 'secondary'"><b>B</b></a-button>
              <a-button @click="cmd('toggleItalic')" :type="isActive('italic') ? 'primary' : 'secondary'"><i>I</i></a-button>
              <a-button @click="cmd('toggleUnderline')" :type="isActive('underline') ? 'primary' : 'secondary'"><u>U</u></a-button>
              <a-button @click="cmd('toggleStrike')" :type="isActive('strike') ? 'primary' : 'secondary'"><s>S</s></a-button>
            </a-button-group>
            <a-button-group size="small">
              <a-button @click="cmd('toggleHeading', { level: 1 })" :type="isActive('heading', { level: 1 }) ? 'primary' : 'secondary'">H1</a-button>
              <a-button @click="cmd('toggleHeading', { level: 2 })" :type="isActive('heading', { level: 2 }) ? 'primary' : 'secondary'">H2</a-button>
              <a-button @click="cmd('toggleHeading', { level: 3 })" :type="isActive('heading', { level: 3 }) ? 'primary' : 'secondary'">H3</a-button>
            </a-button-group>
            <a-button-group size="small">
              <a-button @click="cmd('toggleBulletList')" :type="isActive('bulletList') ? 'primary' : 'secondary'">• 列表</a-button>
              <a-button @click="cmd('toggleOrderedList')" :type="isActive('orderedList') ? 'primary' : 'secondary'">1. 列表</a-button>
              <a-button @click="cmd('toggleBlockquote')" :type="isActive('blockquote') ? 'primary' : 'secondary'">引用</a-button>
              <a-button @click="cmd('toggleCodeBlock')" :type="isActive('codeBlock') ? 'primary' : 'secondary'">代码</a-button>
            </a-button-group>
            <a-button-group size="small">
              <a-button @click="cmd('setTextAlign', 'left')" :type="isActive({ textAlign: 'left' }) ? 'primary' : 'secondary'">左对齐</a-button>
              <a-button @click="cmd('setTextAlign', 'center')" :type="isActive({ textAlign: 'center' }) ? 'primary' : 'secondary'">居中</a-button>
            </a-button-group>
            <a-button-group size="small">
              <a-button @click="setLink">链接</a-button>
              <a-button @click="triggerImage">图片</a-button>
              <a-button @click="cmd('unsetAllMarks'); cmd('clearNodes')">清除格式</a-button>
            </a-button-group>
            <a-button-group size="small">
              <a-button @click="cmd('undo')">撤销</a-button>
              <a-button @click="cmd('redo')">重做</a-button>
            </a-button-group>
            <input ref="imgInput" type="file" accept="image/*" style="display: none" @change="uploadImage" />
          </div>
          <editor-content :editor="editor" class="editor-body" />
        </div>
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
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'

const route = useRoute()
const router = useRouter()
const isNew = computed(() => route.name === 'blog-new')
const form = ref({ title: '', category: '', cover_file_id: null })
const tagsText = ref('')
const saving = ref(false)
const imgInput = ref(null)

const editor = useEditor({
  extensions: [
    StarterKit,
    Underline,
    Image.configure({ inline: false }),
    Link.configure({ openOnClick: false }),
    Placeholder.configure({ placeholder: '开始写作…' }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
  ],
  content: '',
  editorProps: { attributes: { class: 'tiptap' } },
})

function cmd(name, arg) {
  if (!editor.value) return
  const chain = editor.value.chain().focus()
  if (name === 'setTextAlign') chain.setTextAlign(arg).run()
  else if (name === 'toggleHeading') chain.toggleHeading(arg).run()
  else if (name === 'unsetAllMarks') chain.unsetAllMarks().run()
  else if (name === 'clearNodes') chain.clearNodes().run()
  else chain[name]().run()
}
function isActive(name, arg) {
  return editor.value ? editor.value.isActive(name, arg) : false
}
function setLink() {
  if (!editor.value) return
  Modal.confirm({
    title: '插入链接',
    content: () => {
      const input = document.createElement('input')
      input.placeholder = 'https://…'
      input.style.cssText = 'width:100%;padding:8px;border:1px solid #e5e6eb;border-radius:6px'
      input.id = 'tiptap-link-input'
      const wrap = document.createElement('div')
      wrap.appendChild(input)
      return wrap
    },
    onOk: () => {
      const url = document.getElementById('tiptap-link-input')?.value.trim()
      if (url) editor.value.chain().focus().setLink({ href: url }).run()
    },
  })
}
function triggerImage() { imgInput.value?.click() }
async function uploadImage(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !editor.value) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    const meta = await (await apiFetch('/api/files/upload', { method: 'POST', body: fd })).json()
    editor.value.chain().focus().setImage({ src: `/api/files/${meta.id}`, alt: file.name }).run()
    Message.success('图片已插入')
  } catch (err) {
    Message.error(`上传失败：${err.message}`)
  }
}
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
      content_html: editor.value ? editor.value.getHTML() : '',
      // content_md：兼容旧后端（Pydantic 会忽略未知字段，新后端用 content_html）
      content_md: editor.value ? editor.value.getHTML() : '',
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
function toHtml(content) {
  const c = (content || '').trim()
  if (!c) return ''
  return c.startsWith('<') ? c : marked.parse(c) // 兼容旧 Markdown 文章
}
onMounted(async () => {
  if (!isNew.value) {
    try {
      const data = await getJSON('/api/blog/posts?status=draft&limit=200')
      const p = (data.items || []).find((x) => x.id === route.params.id)
        || (await getJSON('/api/blog/posts?limit=200')).items?.find((x) => x.id === route.params.id)
      if (p) {
        const full = await getJSON(`/api/blog/posts/${p.slug}`)
        form.value = { title: full.title, category: full.category || '', cover_file_id: full.cover_file_id }
        tagsText.value = (full.tags || []).join(', ')
        editor.value?.commands.setContent(toHtml(full.content_html || full.content_md || ''))
      }
    } catch (e) { Message.error(`加载失败：${e.message}`) }
  }
})
onBeforeUnmount(() => { editor.value?.destroy() })
</script>

<style scoped>
.editor-wrap { border: 1px solid #e5e6eb; border-radius: 8px; overflow: hidden; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 12px; background: #f7f8fa; border-bottom: 1px solid #e5e6eb; }
.editor-body { min-height: 420px; max-height: 640px; overflow-y: auto; padding: 16px 20px; background: #fff; cursor: text; }
.editor-body :deep(.tiptap) { outline: none; min-height: 380px; line-height: 1.8; font-size: 15px; }
.editor-body :deep(.tiptap p.is-editor-empty:first-child::before) { content: attr(data-placeholder); color: #a9aeb8; float: left; height: 0; pointer-events: none; }
.editor-body :deep(.tiptap h1), .editor-body :deep(.tiptap h2), .editor-body :deep(.tiptap h3) { margin: 1em 0 0.5em; font-weight: 700; }
.editor-body :deep(.tiptap h1) { font-size: 1.6em; } .editor-body :deep(.tiptap h2) { font-size: 1.35em; } .editor-body :deep(.tiptap h3) { font-size: 1.15em; }
.editor-body :deep(.tiptap ul), .editor-body :deep(.tiptap ol) { padding-left: 1.6em; margin: 0.6em 0; }
.editor-body :deep(.tiptap blockquote) { border-left: 3px solid #d3a24a; padding-left: 12px; color: #666; margin: 1em 0; }
.editor-body :deep(.tiptap pre) { background: #1a2340; color: #e8eaf2; padding: 12px 16px; border-radius: 8px; overflow: auto; }
.editor-body :deep(.tiptap pre code) { background: none; color: inherit; padding: 0; }
.editor-body :deep(.tiptap code) { background: #f2f3f5; padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: ui-monospace, monospace; }
.editor-body :deep(.tiptap img) { max-width: 100%; border-radius: 8px; margin: 8px 0; }
.editor-body :deep(.tiptap a) { color: #2f6bff; }
.editor-body :deep(.tiptap hr) { margin: 1.5em 0; border-color: #e5e6eb; }
.editor-body :deep(.tiptap p) { margin: 0.5em 0; }
</style>
