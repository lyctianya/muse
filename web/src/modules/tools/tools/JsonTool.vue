<template>
  <a-space style="margin-bottom: 12px" wrap>
    <a-button @click="fmt">格式化</a-button>
    <a-button @click="minify">压缩</a-button>
    <a-button @click="escape">转义</a-button>
    <a-button @click="unescape">去转义</a-button>
    <a-button @click="copy">复制结果</a-button>
  </a-space>
  <a-textarea v-model="input" :rows="10" placeholder='粘贴 JSON，如 {"a":1}' />
  <a-alert v-if="err" type="error" :content="err" style="margin: 8px 0" />
  <a-textarea v-model="output" :rows="10" placeholder="结果" readonly style="margin-top: 8px" />
</template>
<script setup>
import { ref } from 'vue'
import { Message } from '@arco-design/web-vue'
const input = ref(''), output = ref(''), err = ref('')
function parse() { err.value = ''; return JSON.parse(input.value) }
function fmt() { try { output.value = JSON.stringify(parse(), null, 2) } catch (e) { err.value = e.message } }
function minify() { try { output.value = JSON.stringify(parse()) } catch (e) { err.value = e.message } }
function escape() { output.value = JSON.stringify(input.value).slice(1, -1) }
function unescape() { try { output.value = JSON.parse(`"${input.value}"`) } catch (e) { err.value = e.message } }
function copy() { navigator.clipboard.writeText(output.value).then(() => Message.success('已复制')) }
</script>
