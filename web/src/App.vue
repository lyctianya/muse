<template>
  <a-layout style="min-height: 100vh">
    <a-layout-header style="background: #fff; border-bottom: 1px solid #e5e6eb">
      <div style="display: flex; align-items: center; height: 60px; padding: 0 24px">
        <div style="font-size: 18px; font-weight: 600; margin-right: 32px">📈 股票数据管道</div>
        <a-menu mode="horizontal" :selected-keys="[activeKey]" @menu-item-click="onMenuClick">
          <a-menu-item key="home">市场概览</a-menu-item>
          <a-menu-item key="search">股票搜索</a-menu-item>
          <a-menu-item key="weeks">周文件下载</a-menu-item>
        </a-menu>
        <div style="margin-left: auto; color: #86909c; font-size: 12px">A股 / 港股 / 美股 · 日线（前复权）</div>
      </div>
    </a-layout-header>
    <a-layout-content style="padding: 24px; background: #f2f3f5">
      <router-view />
    </a-layout-content>
  </a-layout>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const activeKey = computed(() => {
  if (route.name === 'weeks') return 'weeks'
  if (route.name === 'search' || route.name === 'chart' || route.name === 'company') return 'search'
  return 'home'
})

function onMenuClick(key) {
  router.push(key === 'weeks' ? '/weeks' : key === 'search' ? '/search' : '/')
}
</script>
