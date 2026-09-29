<template>
  <a-form layout="vertical">
    <a-row :gutter="16">
      <a-col :span="8">
        <a-form-item label="长度"><a-slider v-model="len" :min="6" :max="64" /></a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="字符集">
          <a-checkbox-group v-model="sets">
            <a-checkbox value="lower">小写</a-checkbox>
            <a-checkbox value="upper">大写</a-checkbox>
            <a-checkbox value="digit">数字</a-checkbox>
            <a-checkbox value="symbol">符号</a-checkbox>
          </a-checkbox-group>
        </a-form-item>
      </a-col>
    </a-row>
    <a-button type="primary" @click="gen">生成</a-button>
  </a-form>
  <a-list :data="pwds" style="margin-top: 16px" :bordered="false">
    <a-list-item v-for="(p, i) in pwds" :key="i">
      <a-typography-text copyable code style="font-size: 15px">{{ p }}</a-typography-text>
    </a-list-item>
  </a-list>
</template>
<script setup>
import { ref } from 'vue'
const len = ref(16)
const sets = ref(['lower', 'upper', 'digit', 'symbol'])
const pwds = ref([])
const CHARS = { lower: 'abcdefghijklmnopqrstuvwxyz', upper: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', digit: '0123456789', symbol: '!@#$%^&*()-_=+[]{};:,.<>?' }
function gen() {
  const pool = sets.value.map((s) => CHARS[s]).join('')
  if (!pool) return
  const buf = new Uint32Array(len.value * 5)
  crypto.getRandomValues(buf)
  pwds.value = Array.from({ length: 5 }, (_, k) =>
    Array.from({ length: len.value }, (_, i) => pool[buf[k * len.value + i] % pool.length]).join(''))
}
gen()
</script>
