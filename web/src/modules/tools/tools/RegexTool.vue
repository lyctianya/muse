<template>
  <a-form layout="vertical">
    <a-form-item label="正则表达式">
      <a-input v-model="pattern" placeholder="如 (\d{4})-(\d{2})-(\d{2})" @input="test" />
    </a-form-item>
    <a-form-item>
      <a-space>
        <a-checkbox v-model="flags.g">全局 g</a-checkbox>
        <a-checkbox v-model="flags.i">忽略大小写 i</a-checkbox>
        <a-checkbox v-model="flags.m">多行 m</a-checkbox>
      </a-space>
    </a-form-item>
    <a-form-item label="测试文本">
      <a-textarea v-model="text" :rows="6" placeholder="粘贴要测试的文本" @input="test" />
    </a-form-item>
  </a-form>
  <a-alert v-if="err" type="error" :content="err" style="margin-bottom: 8px" />
  <div v-if="highlighted" class="hl" v-html="highlighted" />
  <a-descriptions v-if="groups.length" :column="1" bordered title="捕获组" style="margin-top: 12px">
    <a-descriptions-item v-for="(g, i) in groups" :key="i" :label="`$${i + 1}`">
      <a-typography-text code>{{ g }}</a-typography-text>
    </a-descriptions-item>
  </a-descriptions>
</template>
<script setup>
import { ref } from 'vue'
const pattern = ref(''), text = ref('')
const flags = ref({ g: true, i: false, m: false })
const err = ref(''), highlighted = ref(''), groups = ref([])
function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;') }
function test() {
  err.value = ''; highlighted.value = ''; groups.value = []
  if (!pattern.value || !text.value) return
  const fl = Object.entries(flags.value).filter(([, v]) => v).map(([k]) => k).join('')
  let re
  try { re = new RegExp(pattern.value, fl) } catch (e) { err.value = '正则不合法：' + e.message; return }
  if (flags.value.g) {
    highlighted.value = esc(text.value).replace(new RegExp(pattern.value, fl), (m) => `<mark>${esc(m)}</mark>`)
  } else {
    const m = text.value.match(re)
    if (m) {
      highlighted.value = esc(text.value).replace(m[0], `<mark>${esc(m[0])}</mark>`)
      groups.value = m.slice(1)
    } else highlighted.value = esc(text.value)
  }
}
</script>
<style scoped>
.hl { border: 1px solid #e5e6eb; border-radius: 6px; padding: 12px; white-space: pre-wrap; font-size: 14px; line-height: 1.8; }
.hl :deep(mark) { background: #ffd166; border-radius: 3px; padding: 0 2px; }
</style>
