<template>
  <a-descriptions :column="1" bordered style="margin-bottom: 16px">
    <a-descriptions-item label="当前时间戳（秒）">{{ nowSec }}</a-descriptions-item>
    <a-descriptions-item label="当前时间戳（毫秒）">{{ nowMs }}</a-descriptions-item>
    <a-descriptions-item label="当前时间">{{ nowStr }}</a-descriptions-item>
  </a-descriptions>
  <a-form layout="vertical">
    <a-form-item label="时间戳 → 日期">
      <a-space>
        <a-input v-model="ts" placeholder="如 1727000000" style="width: 240px" />
        <a-select v-model="unit" style="width: 120px"><a-option value="s">秒</a-option><a-option value="ms">毫秒</a-option></a-select>
        <a-button @click="ts2date">转换</a-button>
      </a-space>
      <div v-if="dateOut" style="margin-top: 8px">{{ dateOut }}</div>
    </a-form-item>
    <a-form-item label="日期 → 时间戳">
      <a-space>
        <a-input v-model="dateIn" placeholder="如 2026-09-29 20:00:00" style="width: 240px" />
        <a-button @click="date2ts">转换</a-button>
      </a-space>
      <div v-if="tsOut" style="margin-top: 8px">秒：{{ tsOut.s }}　毫秒：{{ tsOut.ms }}</div>
    </a-form-item>
  </a-form>
</template>
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
const nowSec = ref(0), nowMs = ref(0), nowStr = ref('')
const ts = ref(''), unit = ref('s'), dateOut = ref('')
const dateIn = ref(''), tsOut = ref(null)
let timer = null
function tick() {
  const n = new Date()
  nowSec.value = Math.floor(n.getTime() / 1000)
  nowMs.value = n.getTime()
  nowStr.value = n.toLocaleString('zh-CN')
}
function ts2date() {
  const v = Number(ts.value)
  if (!v) return
  const d = new Date(unit.value === 's' ? v * 1000 : v)
  dateOut.value = d.toLocaleString('zh-CN') + '（本地） / ' + d.toISOString() + '（UTC）'
}
function date2ts() {
  const d = new Date(dateIn.value.replace(/-/g, '/'))
  if (isNaN(d)) { tsOut.value = null; return }
  tsOut.value = { s: Math.floor(d.getTime() / 1000), ms: d.getTime() }
}
onMounted(() => { tick(); timer = setInterval(tick, 1000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
