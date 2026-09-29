<template>
  <a-space align="start" :size="24">
    <input type="color" v-model="hex" style="width: 120px; height: 120px; border: none; cursor: pointer" />
    <a-descriptions :column="1" bordered style="min-width: 320px">
      <a-descriptions-item label="HEX"><a-typography-text copyable code>{{ hex }}</a-typography-text></a-descriptions-item>
      <a-descriptions-item label="RGB"><a-typography-text copyable code>{{ rgb }}</a-typography-text></a-descriptions-item>
      <a-descriptions-item label="HSL"><a-typography-text copyable code>{{ hsl }}</a-typography-text></a-descriptions-item>
      <a-descriptions-item label="CSS">
        <div :style="{ width: 120, height: 32, background: hex, borderRadius: 6, border: '1px solid #e5e6eb' }" />
      </a-descriptions-item>
    </a-descriptions>
  </a-space>
  <a-form-item label="输入色值转换" style="margin-top: 16px; max-width: 400px">
    <a-input v-model="raw" placeholder="如 #d3a24a 或 211,162,74" @input="parse" />
    <div v-if="err" style="color: #f53f3f; font-size: 12px; margin-top: 4px">{{ err }}</div>
  </a-form-item>
</template>
<script setup>
import { ref, computed } from 'vue'
const hex = ref('#d3a24a')
const raw = ref('')
const err = ref('')
const rgb = computed(() => {
  const n = parseInt(hex.value.slice(1), 16)
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
})
const hsl = computed(() => {
  let [r, g, b] = rgb.value.split(', ').map((v) => v / 255)
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h = 0, s = 0
  const l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
    else if (max === g) h = ((b - r) / d + 2) / 6
    else h = ((r - g) / d + 4) / 6
  }
  return `${Math.round(h * 360)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%`
})
function parse() {
  err.value = ''
  const v = raw.value.trim()
  const mHex = v.match(/^#?([0-9a-fA-F]{6})$/)
  const mRgb = v.match(/^(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})$/)
  if (mHex) hex.value = '#' + mHex[1].toLowerCase()
  else if (mRgb && mRgb.slice(1).every((x) => x <= 255)) {
    hex.value = '#' + mRgb.slice(1).map((x) => Number(x).toString(16).padStart(2, '0')).join('')
  } else if (v) err.value = '格式不对，试试 #d3a24a 或 211,162,74'
}
</script>
