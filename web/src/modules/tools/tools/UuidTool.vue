<template>
  <a-space style="margin-bottom: 16px" wrap>
    <a-button type="primary" @click="gen(1)">生成 1 个</a-button>
    <a-button @click="gen(5)">生成 5 个</a-button>
    <a-button @click="gen(10)">生成 10 个</a-button>
    <a-checkbox v-model="noDash">去掉连字符</a-checkbox>
    <a-checkbox v-model="upper">大写</a-checkbox>
  </a-space>
  <a-list :data="ids" :bordered="false">
    <a-list-item v-for="(id, i) in ids" :key="i">
      <a-typography-text copyable code style="font-size: 14px">{{ id }}</a-typography-text>
    </a-list-item>
  </a-list>
</template>
<script setup>
import { ref } from 'vue'
const ids = ref([])
const noDash = ref(false)
const upper = ref(false)
function gen(n) {
  ids.value = Array.from({ length: n }, () => {
    let id = crypto.randomUUID()
    if (noDash.value) id = id.replace(/-/g, '')
    if (upper.value) id = id.toUpperCase()
    return id
  })
}
gen(5)
</script>
