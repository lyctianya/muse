<template>
  <div class="ai-models">
    <div class="ai-models-head">
      <h2>模型配置</h2>
      <a-button type="primary" @click="openEdit(null)">
        <template #icon><icon-plus /></template>添加模型
      </a-button>
    </div>
    <p class="ai-models-desc">
      支持 OpenAI 兼容接口（DeepSeek / Kimi / Qwen / GLM / 硅基流动 / Ollama 等）。
      API Key 加密存储，前端仅显示脱敏形式。设为"共享"后所有用户可用（需 ai:manage 权限）。
    </p>

    <a-table :data="models" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="名称" data-index="name" />
        <a-table-column title="模型 ID" data-index="model_id" />
        <a-table-column title="Base URL" data-index="base_url" :ellipsis="true" :tooltip="true" />
        <a-table-column title="Key" width="130">
          <template #cell="{ record }">
            <span v-if="record.has_key" class="ai-key">{{ record.api_key_masked }}</span>
            <span v-else class="ai-nokey">未设置</span>
          </template>
        </a-table-column>
        <a-table-column title="范围" width="90">
          <template #cell="{ record }">
            <a-tag :color="record.shared ? 'blue' : 'green'">{{ record.shared ? '共享' : '个人' }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="启用" width="80">
          <template #cell="{ record }">
            <a-switch v-model="record.enabled" size="small" @change="toggleEnabled(record)" />
          </template>
        </a-table-column>
        <a-table-column title="操作" width="140">
          <template #cell="{ record }">
            <a-button size="mini" type="text" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm content="确定删除该模型？" @ok="removeModel(record)">
              <a-button size="mini" type="text" status="danger">删除</a-button>
            </a-popconfirm>
          </template>
        </a-table-column>
      </template>
    </a-table>

    <a-modal v-model:visible="editVisible" :title="editId ? '编辑模型' : '添加模型'"
             @ok="saveModel" @cancel="editVisible = false" :ok-loading="saving">
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model="form.name" placeholder="如：DeepSeek V3" />
        </a-form-item>
        <a-form-item label="Base URL" required>
          <a-input v-model="form.base_url" placeholder="如：https://api.deepseek.com/v1" />
        </a-form-item>
        <a-form-item label="Model ID" required>
          <a-input v-model="form.model_id" placeholder="如：deepseek-chat" />
        </a-form-item>
        <a-form-item label="API Key">
          <a-input-password v-model="form.api_key"
            :placeholder="editId ? '留空则不修改' : 'sk-...'" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model="form.sort_order" :min="0" />
        </a-form-item>
        <a-form-item>
          <a-checkbox v-model="form.shared" :disabled="!canManage && !form.shared">
            共享模型（所有用户可用）
          </a-checkbox>
          <span v-if="!canManage" class="ai-tip">需要 ai:manage 权限</span>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getJSON, postJSON, putJSON, del } from '../../../platform/utils/api.js'
import { hasPerm } from '../../../platform/utils/auth.js'

const canManage = hasPerm('ai:manage')

const models = ref([])
const loading = ref(false)
const editVisible = ref(false)
const editId = ref(null)
const saving = ref(false)
const form = ref({ name: '', base_url: '', model_id: '', api_key: '', sort_order: 0, shared: false })

async function load() {
  loading.value = true
  try { models.value = await getJSON('/api/ai/models') }
  catch (e) { Message.error(e.message) }
  finally { loading.value = false }
}
function openEdit(record) {
  editId.value = record ? record.id : null
  form.value = record
    ? { name: record.name, base_url: record.base_url, model_id: record.model_id,
        api_key: '', sort_order: record.sort_order, shared: record.shared }
    : { name: '', base_url: '', model_id: '', api_key: '', sort_order: 0, shared: false }
  editVisible.value = true
}
async function saveModel() {
  if (!form.value.name.trim() || !form.value.base_url.trim() || !form.value.model_id.trim()) {
    Message.warning('请填写名称、Base URL 和 Model ID')
    return
  }
  saving.value = true
  try {
    if (editId.value) await putJSON(`/api/ai/models/${editId.value}`, form.value)
    else await postJSON('/api/ai/models', form.value)
    Message.success('已保存')
    editVisible.value = false
    await load()
  } catch (e) { Message.error(e.message) }
  finally { saving.value = false }
}
async function toggleEnabled(record) {
  try {
    await putJSON(`/api/ai/models/${record.id}`, { ...record, api_key: '' })
  } catch (e) { Message.error(e.message); record.enabled = !record.enabled }
}
async function removeModel(record) {
  try {
    await del(`/api/ai/models/${record.id}`)
    Message.success('已删除')
    await load()
  } catch (e) { Message.error(e.message) }
}
onMounted(load)
</script>

<style scoped>
.ai-models { padding: 24px 32px; max-width: 1100px; }
.ai-models-head { display: flex; justify-content: space-between; align-items: center; }
.ai-models-head h2 { margin: 0; font-size: 18px; }
.ai-models-desc { color: #86909c; font-size: 13px; margin: 8px 0 16px; }
.ai-key { font-family: Consolas, monospace; font-size: 12px; }
.ai-nokey { color: #c9cdd4; font-size: 12px; }
.ai-tip { color: #86909c; font-size: 12px; margin-left: 8px; }
</style>
