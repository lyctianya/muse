<template>
  <a-tooltip :content="inWatch ? '取消自选' : '加入自选'">
    <a-button shape="circle" :loading="busy" @click="toggle">
      <template #icon>
        <icon-star-fill v-if="inWatch" style="color: #ffb400" />
        <icon-star v-else />
      </template>
    </a-button>
  </a-tooltip>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconStar, IconStarFill } from '@arco-design/web-vue/es/icon'

const props = defineProps({ market: { type: String, default: 'cn' }, symbol: String })

const inWatch = ref(false)
const busy = ref(false)

async function refresh() {
  try {
    const res = await fetch('/api/watchlist')
    const list = await res.json()
    inWatch.value = list.some(
      (w) => w.market === props.market && w.symbol === props.symbol)
  } catch (e) { /* 忽略，后端未建表时保持未加入状态 */ }
}

async function toggle() {
  busy.value = true
  try {
    if (inWatch.value) {
      const q = new URLSearchParams({ market: props.market, symbol: props.symbol })
      const res = await fetch(`/api/watchlist?${q}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('删除失败')
      inWatch.value = false
      Message.success('已取消自选')
    } else {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ market: props.market, symbol: props.symbol }),
      })
      if (!res.ok) throw new Error('加入失败')
      inWatch.value = true
      Message.success('已加入自选')
    }
  } catch (e) {
    Message.error(e.message)
  } finally {
    busy.value = false
  }
}

onMounted(refresh)
</script>
