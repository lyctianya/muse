<template>
  <a-textarea v-model="input" :rows="6" placeholder="输入文本或 URL" />
  <a-space style="margin: 8px 0" wrap>
    <a-button @click="doEncode(false)">encodeURI 编码</a-button>
    <a-button @click="doEncode(true)">encodeURIComponent 编码</a-button>
    <a-button @click="doDecode(false)">decodeURI 解码</a-button>
    <a-button @click="doDecode(true)">decodeURIComponent 解码</a-button>
  </a-space>
  <a-alert v-if="err" type="error" :content="err" style="margin-bottom: 8px" />
  <a-textarea v-model="output" :rows="6" placeholder="结果" readonly />
</template>
<script setup>
import { ref } from 'vue'
const input = ref(''), output = ref(''), err = ref('')
function run(fn) { err.value = ''; try { output.value = fn(input.value) } catch { err.value = '转换失败，输入不合法' } }
const doEncode = (full) => run((s) => full ? encodeURIComponent(s) : encodeURI(s))
const doDecode = (full) => run((s) => full ? decodeURIComponent(s) : decodeURI(s))
</script>
