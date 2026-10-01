<template>
  <div class="ai-chat">
    <!-- 左侧会话列表 -->
    <div class="ai-side">
      <div class="ai-side-head">
        <a-button type="primary" long @click="newChat">
          <template #icon><icon-plus /></template>新对话
        </a-button>
        <a-input-search v-model="keyword" placeholder="搜索会话" size="small" style="margin-top:8px" />
      </div>
      <div class="ai-conv-list">
        <div v-if="pinnedList.length" class="ai-group">置顶</div>
        <div v-for="c in pinnedList" :key="c.id" class="ai-conv"
             :class="{ active: c.id === curId }" @click="openConv(c.id)">
          <span class="ai-conv-title">{{ c.title }}</span>
          <a-dropdown @select="(v) => onConvMenu(v, c)" position="br">
            <span class="ai-conv-more" @click.stop><icon-more /></span>
            <template #content>
              <a-doption value="unpin">取消置顶</a-doption>
              <a-doption value="rename">改名</a-doption>
              <a-doption value="del"><span style="color:#f53f3f">删除</span></a-doption>
            </template>
          </a-dropdown>
        </div>
        <div v-if="normalList.length" class="ai-group">最近</div>
        <div v-for="c in normalList" :key="c.id" class="ai-conv"
             :class="{ active: c.id === curId }" @click="openConv(c.id)">
          <span class="ai-conv-title">{{ c.title }}</span>
          <a-dropdown @select="(v) => onConvMenu(v, c)" position="br">
            <span class="ai-conv-more" @click.stop><icon-more /></span>
            <template #content>
              <a-doption value="pin">置顶</a-doption>
              <a-doption value="rename">改名</a-doption>
              <a-doption value="del"><span style="color:#f53f3f">删除</span></a-doption>
            </template>
          </a-dropdown>
        </div>
        <a-empty v-if="!filtered.length" description="暂无会话" />
      </div>
      <div class="ai-side-foot">
        <a-button size="small" long @click="$router.push('/ai/models')">
          <template #icon><icon-settings /></template>模型配置
        </a-button>
      </div>
    </div>

    <!-- 改名弹窗 -->
    <a-modal v-model:visible="renameVisible" title="重命名会话" @ok="doRename" @cancel="renameVisible = false">
      <a-input v-model="renameText" placeholder="会话名称" :max-length="100" />
    </a-modal>

    <!-- 右侧对话区 -->
    <div class="ai-main">
      <div class="ai-top">
        <a-select v-model="modelId" placeholder="选择模型" style="width:260px" size="small"
                  :loading="modelsLoading" @change="onModelChange">
          <a-optgroup label="共享模型">
            <a-option v-for="m in sharedModels" :key="m.id" :value="m.id">{{ m.name }}</a-option>
          </a-optgroup>
          <a-optgroup label="我的模型">
            <a-option v-for="m in myModels" :key="m.id" :value="m.id">{{ m.name }}</a-option>
          </a-optgroup>
        </a-select>
        <span v-if="!models.length && !modelsLoading" class="ai-nomodel">
          未配置模型，<a @click="$router.push('/ai/models')">去配置</a>
        </span>
      </div>

      <div ref="msgBox" class="ai-msgs">
        <div v-for="m in messages" :key="m.id" class="ai-msg" :class="m.role">
          <div class="ai-avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
          <div class="ai-bubble">
            <div v-if="m.role === 'user'" class="ai-text">{{ m.content }}</div>
            <div v-else class="ai-md" v-html="renderMd(m.content)" />
            <div v-if="m.role === 'assistant' && m === messages[messages.length-1] && !streaming"
                 class="ai-actions">
              <a-button size="mini" type="text" @click="regenerate">重新生成</a-button>
              <a-button size="mini" type="text" @click="copyText(m.content)">复制</a-button>
            </div>
          </div>
        </div>
        <div v-if="streaming && !streamText" class="ai-msg assistant">
          <div class="ai-avatar">AI</div>
          <div class="ai-bubble"><a-spin :size="16" /></div>
        </div>
        <a-empty v-if="!messages.length && !streaming" description="输入消息开始对话" />
      </div>

      <div class="ai-input">
        <a-textarea v-model="input" placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                    :auto-size="{ minRows: 2, maxRows: 6 }"
                    @keydown.enter.exact.prevent="send" :disabled="streaming" />
        <div class="ai-input-bar">
          <span class="ai-hint">上下文最近 {{ contextLen }} 条</span>
          <a-button v-if="streaming" type="primary" status="danger" @click="stop">停止</a-button>
          <a-button v-else type="primary" @click="send" :disabled="!input.trim() || !modelId">发送</a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { marked } from 'marked'
import { Message, Modal } from '@arco-design/web-vue'
import { getJSON, postJSON, putJSON, del, apiFetch } from '../../../platform/utils/api.js'

const conversations = ref([])
const messages = ref([])
const models = ref([])
const modelsLoading = ref(false)
const curId = ref(null)
const modelId = ref('')
const input = ref('')
const keyword = ref('')
const streaming = ref(false)
const streamText = ref('')
const contextLen = ref(20)
const msgBox = ref(null)
let aborter = null

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return conversations.value
  return conversations.value.filter((c) => c.title.toLowerCase().includes(k))
})
const pinnedList = computed(() => filtered.value.filter((c) => c.pinned))
const normalList = computed(() => filtered.value.filter((c) => !c.pinned))
const sharedModels = computed(() => models.value.filter((m) => m.shared))
const myModels = computed(() => models.value.filter((m) => !m.shared))

function renderMd(src) {
  try { return marked.parse(src || '') } catch { return src }
}
function scrollBottom() {
  nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
}
function copyText(t) {
  navigator.clipboard.writeText(t).then(() => Message.success('已复制'))
}

async function loadModels() {
  modelsLoading.value = true
  try {
    models.value = await getJSON('/api/ai/models')
    if (!modelId.value && models.value.length) modelId.value = models.value[0].id
  } catch (e) { Message.error('模型加载失败：' + e.message) }
  finally { modelsLoading.value = false }
}
async function loadConvs() {
  try { conversations.value = await getJSON('/api/ai/conversations') }
  catch (e) { Message.error('会话加载失败：' + e.message) }
}
async function openConv(id) {
  if (streaming.value) stop()
  curId.value = id
  messages.value = []
  try {
    const conv = conversations.value.find((c) => c.id === id)
    if (conv && conv.model_id) modelId.value = conv.model_id
    messages.value = await getJSON(`/api/ai/conversations/${id}/messages`)
    scrollBottom()
  } catch (e) { Message.error(e.message) }
}
function newChat() {
  if (streaming.value) stop()
  curId.value = null
  messages.value = []
  input.value = ''
}
function onModelChange() {
  if (curId.value) putJSON(`/api/ai/conversations/${curId.value}`, { model_id: modelId.value }).catch(() => {})
}
async function onConvMenu(action, c) {
  if (action === 'del') {
    Modal.confirm({
      title: '删除会话', content: `确定删除「${c.title}」吗？消息将一并删除。`,
      okButtonProps: { status: 'danger' },
      onOk: async () => {
        await del(`/api/ai/conversations/${c.id}`)
        conversations.value = conversations.value.filter((x) => x.id !== c.id)
        if (curId.value === c.id) newChat()
        Message.success('已删除')
      },
    })
  } else if (action === 'pin' || action === 'unpin') {
    await putJSON(`/api/ai/conversations/${c.id}`, { pinned: action === 'pin' })
    c.pinned = action === 'pin'
    sortConvs()
  } else if (action === 'rename') {
    renameTarget.value = c
    renameText.value = c.title
    renameVisible.value = true
  }
}
const renameVisible = ref(false)
const renameText = ref('')
const renameTarget = ref(null)
async function doRename() {
  const c = renameTarget.value
  if (!c) return
  await putJSON(`/api/ai/conversations/${c.id}`, { title: renameText.value })
  c.title = renameText.value || '新对话'
  renameVisible.value = false
}
function sortConvs() {
  conversations.value.sort((a, b) => (b.pinned - a.pinned) || (b.updated_at > a.updated_at ? 1 : -1))
}

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value || !modelId.value) return
  if (!models.value.length) { Message.warning('请先配置模型'); return }
  input.value = ''
  // 乐观追加用户消息
  const userMsg = { id: 'tmp-u-' + Date.now(), role: 'user', content: text }
  messages.value.push(userMsg)
  scrollBottom()
  streaming.value = true
  streamText.value = ''
  const aiMsg = { id: 'tmp-a-' + Date.now(), role: 'assistant', content: '' }
  messages.value.push(aiMsg)
  aborter = new AbortController()
  try {
    const res = await apiFetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: curId.value, model_id: modelId.value,
        content: text, context_len: contextLen.value,
      }),
      signal: aborter.signal,
    })
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop()
      for (const p of parts) {
        const line = p.trim()
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (data === '[DONE]') continue
        try {
          const ev = JSON.parse(data)
          if (ev.type === 'meta' && ev.conversation_id) {
            if (!curId.value) {
              curId.value = ev.conversation_id
              await loadConvs()
            }
          } else if (ev.type === 'delta') {
            aiMsg.content += ev.text
            streamText.value = aiMsg.content
            scrollBottom()
          } else if (ev.type === 'error') {
            Message.error(ev.message)
          }
        } catch { /* ignore */ }
      }
    }
    // 流结束：用服务端落库 id 替换临时消息（简化：重新拉取）
    if (curId.value) {
      const fresh = await getJSON(`/api/ai/conversations/${curId.value}/messages`)
      messages.value = fresh
      await loadConvs()
    }
  } catch (e) {
    if (e.name !== 'AbortError') Message.error('请求失败：' + e.message)
    messages.value = messages.value.filter((m) => m !== aiMsg)
  } finally {
    streaming.value = false
    streamText.value = ''
    aborter = null
    scrollBottom()
  }
}
function stop() { if (aborter) aborter.abort() }
async function regenerate() {
  // 删掉最后一条 assistant 回复，按最后一条 user 重发
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  if (!lastUser || streaming.value) return
  messages.value = messages.value.filter((m) => m.role !== 'assistant' || m.id !== messages.value[messages.value.length - 1].id)
  input.value = lastUser.content
  // 注意：后端历史里仍有上一轮 assistant 消息，会作为上下文；可接受
  await send()
}

watch(messages, scrollBottom)
onMounted(async () => {
  await Promise.all([loadModels(), loadConvs()])
})
</script>

<style scoped>
.ai-chat { display: flex; height: calc(100vh - 64px); background: #fff; }
.ai-side { width: 260px; border-right: 1px solid #e5e6eb; display: flex; flex-direction: column; }
.ai-side-head { padding: 12px; border-bottom: 1px solid #f2f3f5; }
.ai-conv-list { flex: 1; overflow-y: auto; padding: 8px; }
.ai-group { font-size: 12px; color: #86909c; padding: 8px 8px 4px; }
.ai-conv { display: flex; align-items: center; padding: 8px 10px; border-radius: 6px; cursor: pointer; }
.ai-conv:hover { background: #f2f3f5; }
.ai-conv.active { background: #e8f3ff; }
.ai-conv-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.ai-conv-more { color: #86909c; padding: 2px 4px; border-radius: 4px; }
.ai-conv-more:hover { background: #e5e6eb; }
.ai-side-foot { padding: 12px; border-top: 1px solid #f2f3f5; }
.ai-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.ai-top { padding: 10px 16px; border-bottom: 1px solid #f2f3f5; display: flex; align-items: center; gap: 8px; }
.ai-nomodel { font-size: 13px; color: #86909c; }
.ai-msgs { flex: 1; overflow-y: auto; padding: 16px 24px; }
.ai-msg { display: flex; gap: 12px; margin-bottom: 18px; }
.ai-avatar { width: 32px; height: 32px; border-radius: 50%; background: #165dff; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0; }
.ai-msg.user .ai-avatar { background: #00b42a; }
.ai-bubble { flex: 1; min-width: 0; }
.ai-msg.user .ai-bubble { background: #f2f3f5; border-radius: 8px; padding: 10px 14px; }
.ai-text { white-space: pre-wrap; font-size: 14px; line-height: 1.7; }
.ai-md { font-size: 14px; line-height: 1.7; }
.ai-md :deep(pre) { background: #f2f3f5; border-radius: 6px; padding: 12px; overflow-x: auto; }
.ai-md :deep(code) { font-family: Consolas, monospace; font-size: 13px; }
.ai-md :deep(p) { margin: 0 0 8px; }
.ai-md :deep(ul), .ai-md :deep(ol) { padding-left: 20px; margin: 0 0 8px; }
.ai-md :deep(table) { border-collapse: collapse; margin: 8px 0; }
.ai-md :deep(th), .ai-md :deep(td) { border: 1px solid #e5e6eb; padding: 6px 10px; }
.ai-actions { margin-top: 6px; }
.ai-input { padding: 12px 24px 16px; border-top: 1px solid #f2f3f5; }
.ai-input-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.ai-hint { font-size: 12px; color: #86909c; }
</style>
