<template>
  <a-form layout="vertical">
    <a-form-item label="内容">
      <a-textarea v-model="text" :rows="4" placeholder="输入文本 / 链接，生成二维码" @input="gen" />
    </a-form-item>
    <a-row :gutter="16">
      <a-col :span="8">
        <a-form-item label="尺寸"><a-slider v-model="size" :min="120" :max="480" @change="gen" /></a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="前景色"><a-input v-model="fg" @input="gen" /></a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="背景色"><a-input v-model="bg" @input="gen" /></a-form-item>
      </a-col>
    </a-row>
  </a-form>
  <div style="text-align: center; margin-top: 8px">
    <img v-if="url" :src="url" :width="size" :height="size" alt="二维码" />
    <div v-if="url" style="margin-top: 8px"><a-button @click="download">下载 PNG</a-button></div>
    <a-empty v-else description="输入内容后生成" />
  </div>
</template>
<script setup>
import { ref } from 'vue'
import QRCode from 'qrcode'
const text = ref(''), url = ref('')
const size = ref(240), fg = ref('#1a2340'), bg = ref('#ffffff')
let timer = null
function gen() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    if (!text.value.trim()) { url.value = ''; return }
    url.value = await QRCode.toDataURL(text.value, {
      width: size.value, color: { dark: fg.value, light: bg.value }, margin: 2,
    })
  }, 300)
}
function download() {
  const a = document.createElement('a')
  a.href = url.value
  a.download = 'qrcode.png'
  a.click()
}
</script>
