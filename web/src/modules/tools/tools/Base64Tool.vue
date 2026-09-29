<template>
  <a-tabs default-active-key="enc">
    <a-tab-pane key="enc" title="编码">
      <a-textarea v-model="raw" :rows="8" placeholder="输入要编码的文本" />
      <a-button type="primary" @click="encode" style="margin: 8px 0">编码 →</a-button>
      <a-textarea v-model="b64" :rows="8" placeholder="Base64 结果" readonly />
    </a-tab-pane>
    <a-tab-pane key="dec" title="解码">
      <a-textarea v-model="b64in" :rows="8" placeholder="输入 Base64" />
      <a-button type="primary" @click="decode" style="margin: 8px 0">解码 →</a-button>
      <a-alert v-if="err" type="error" :content="err" style="margin-bottom: 8px" />
      <a-textarea v-model="rawOut" :rows="8" placeholder="解码结果" readonly />
    </a-tab-pane>
  </a-tabs>
</template>
<script setup>
import { ref } from 'vue'
const raw = ref(''), b64 = ref(''), b64in = ref(''), rawOut = ref(''), err = ref('')
const enc = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)))
const dec = (s) => new TextDecoder().decode(Uint8Array.from(atob(s), (c) => c.charCodeAt(0)))
function encode() { b64.value = enc(raw.value) }
function decode() { err.value = ''; try { rawOut.value = dec(b64in.value.trim()) } catch (e) { err.value = 'Base64 不合法' } }
</script>
