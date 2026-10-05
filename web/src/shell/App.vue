<template>
  <a-layout class="app-shell" v-if="route.name !== 'login' && route.name !== 'hub'">
    <a-layout-sider
      :width="224"
      :collapsed-width="64"
      collapsible
      :hide-trigger="true"
      v-model:collapsed="collapsed"
      class="app-sider"
    >
      <div class="sider-inner">
        <div class="logo">
          <span class="logo-mark">◆</span>
          <span class="logo-text" v-show="!collapsed">股票数据管道</span>
        </div>
        <a-menu
          mode="vertical"
          theme="light"
          :selected-keys="[activeKey]"
          :collapsed="collapsed"
          @menu-item-click="onMenuClick"
          class="side-menu"
        >
          <a-menu-item key="hub"><template #icon><icon-compass /></template>3D 菜单</a-menu-item>
          <a-menu-item v-if="can('market:view')" key="home"><template #icon><icon-dashboard /></template>市场概览</a-menu-item>
          <a-menu-item v-if="can('quotes:view')" key="search"><template #icon><icon-search /></template>股票搜索</a-menu-item>
          <a-menu-item v-if="can('screener:use')" key="screener"><template #icon><icon-filter /></template>策略选股</a-menu-item>
          <a-menu-item v-if="can('watchlist:use')" key="watchlist"><template #icon><icon-star /></template>自选股</a-menu-item>
          <a-menu-item v-if="can('extra:view')" key="extra"><template #icon><icon-layers /></template>市场深度</a-menu-item>
          <a-menu-item v-if="can('weeks:download')" key="weeks"><template #icon><icon-download /></template>周文件下载</a-menu-item>
          <a-menu-item v-if="can('sync:view')" key="sync"><template #icon><icon-sync /></template>数据更新</a-menu-item>
          <a-menu-item v-if="can('users:manage')" key="users"><template #icon><icon-user /></template>用户管理</a-menu-item>
          <a-menu-item v-if="can('files:view')" key="files"><template #icon><icon-folder /></template>文件管理</a-menu-item>
          <a-menu-item v-if="can('blog:view')" key="blog"><template #icon><icon-edit /></template>博客</a-menu-item>
          <a-menu-item v-if="can('gallery:view')" key="gallery"><template #icon><icon-image /></template>相册</a-menu-item>
          <a-menu-item v-if="can('game:view')" key="game"><template #icon><icon-trophy /></template>游戏</a-menu-item>
          <a-menu-item v-if="can('news60s:view')" key="news60s"><template #icon><icon-notification /></template>60秒新闻</a-menu-item>
          <a-menu-item v-if="can('tools:use')" key="tools"><template #icon><icon-tool /></template>工具箱</a-menu-item>
        </a-menu>
      </div>

      <button
        type="button"
        class="sider-float-toggle"
        :title="collapsed ? '展开导航' : '收起导航'"
        @click="collapsed = !collapsed"
      >
        <icon-menu-unfold v-if="collapsed" />
        <icon-menu-fold v-else />
      </button>
    </a-layout-sider>

    <a-layout class="app-main">
      <a-layout-header class="app-header">
        <div class="page-title">{{ pageTitle }}</div>
        <div class="header-right">
          <a-tag color="gold">{{ today }}</a-tag>
          <a-dropdown v-if="authState.user" @select="onUserMenu">
            <a-button size="small">
              <template #icon><icon-user /></template>
              {{ authState.user.display_name }}
            </a-button>
            <template #content>
              <a-doption value="logout">退出登录</a-doption>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>
      <a-layout-content class="app-content">
        <div class="page-wrap" :class="{ 'page-wrap--fill': route.name === 'news60s' }">
          <router-view :key="$route.fullPath" />
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
  <router-view v-else :key="$route.fullPath" />
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IconDashboard, IconSearch, IconFilter, IconStar,
  IconLayers, IconDownload, IconSync, IconUser, IconFolder,
  IconEdit, IconImage, IconTrophy, IconTool, IconCompass, IconNotification,
  IconMenuFold, IconMenuUnfold,
} from '@arco-design/web-vue/es/icon'
import { fmtDateLocal } from '../platform/utils/date.js'
import { authState, hasPerm, logout } from '../platform/utils/auth.js'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

const NAV = {
  hub: '3D 菜单', home: '市场概览', search: '股票搜索', weeks: '周文件下载', extra: '市场深度',
  sync: '数据更新', screener: '策略选股', watchlist: '自选股', users: '用户管理',
  files: '文件管理', chart: 'K线行情', company: '公司详情',
  blog: '博客', gallery: '相册', game: '游戏', news60s: '60秒新闻', tools: '工具箱',
}
const can = (perm) => hasPerm(perm)
const activeKey = computed(() => {
  if (route.name === 'weeks') return 'weeks'
  if (route.name === 'extra') return 'extra'
  if (route.name === 'sync') return 'sync'
  if (route.name === 'screener') return 'screener'
  if (route.name === 'watchlist') return 'watchlist'
  if (route.name === 'users') return 'users'
  if (route.name === 'files') return 'files'
  if (route.name === 'blog' || route.name === 'blog-post' || route.name === 'blog-new' || route.name === 'blog-edit') return 'blog'
  if (route.name === 'gallery' || route.name === 'album') return 'gallery'
  if (route.name === 'game') return 'game'
  if (route.name === 'news60s') return 'news60s'
  if (route.name === 'tools') return 'tools'
  if (route.name === 'hub') return 'hub'
  if (route.name === 'search' || route.name === 'chart' || route.name === 'company') return 'search'
  return 'home'
})
const pageTitle = computed(() => {
  if ((route.name === 'chart' || route.name === 'company') && route.query.name)
    return `${route.query.name} ${route.params.symbol || ''}`
  return NAV[activeKey.value] || '市场概览'
})
const today = computed(() => fmtDateLocal(new Date()))

function onMenuClick(key) {
  const paths = {
    weeks: '/weeks', extra: '/extra', sync: '/sync', screener: '/screener',
    watchlist: '/watchlist', search: '/search', users: '/users', files: '/files',
    blog: '/blog', gallery: '/gallery', game: '/game', news60s: '/60s', tools: '/tools',
    hub: '/', home: '/market',
  }
  router.push(paths[key] || '/')
}

function onUserMenu(v) {
  if (v === 'logout') {
    logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-shell {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  background: var(--bg);
}

.app-sider {
  position: relative !important;
  height: 100vh !important;
  max-height: 100vh !important;
  overflow: visible !important;
  background: #f7f8fb !important;
  border-right: 1px solid var(--border);
  z-index: 20;
}
.app-sider :deep(.arco-layout-sider-children) {
  height: 100%;
  overflow: visible;
  background: transparent;
}
.sider-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f7f8fb;
}

.sider-float-toggle {
  position: absolute;
  top: 50%;
  right: -12px;
  transform: translateY(-50%);
  z-index: 30;
  width: 24px;
  height: 48px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--text-2);
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.08);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.sider-float-toggle:hover {
  color: var(--gold);
  border-color: rgba(211, 162, 74, 0.55);
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.12);
}
.sider-float-toggle :deep(svg) {
  font-size: 14px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 20px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
}
.logo-mark { color: var(--gold); font-size: 18px; line-height: 1; }
.logo-text {
  color: var(--ink);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.side-menu {
  flex: 1;
  min-height: 0;
  background: transparent !important;
  padding: 10px 0 12px;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.side-menu::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}
.side-menu :deep(.arco-menu-inner) {
  padding: 0 !important;
}
.side-menu :deep(.arco-menu-item) {
  color: var(--text-2) !important;
  margin: 2px 10px !important;
  border-radius: 10px !important;
  width: auto !important;
  background: transparent !important;
}
.side-menu :deep(.arco-menu-item .arco-icon) {
  color: var(--text-3);
}
.side-menu :deep(.arco-menu-item:hover) {
  color: var(--text-1) !important;
  background: rgba(26, 35, 64, 0.05) !important;
}
.side-menu :deep(.arco-menu-item:hover .arco-icon) {
  color: var(--gold);
}
.side-menu :deep(.arco-menu-selected) {
  color: var(--ink) !important;
  background: var(--gold-soft) !important;
  font-weight: 650;
  position: relative;
}
.side-menu :deep(.arco-menu-selected .arco-icon) {
  color: var(--gold);
}
.side-menu :deep(.arco-menu-selected)::before {
  content: "";
  position: absolute;
  left: -10px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 2px;
  background: var(--gold);
}

.app-main {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.app-header {
  flex-shrink: 0;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 56px !important;
  line-height: 56px !important;
}
.page-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 20px 24px 24px;
  background: var(--bg);
  scrollbar-width: thin;
}

.page-wrap {
  max-width: 1440px;
  margin: 0 auto;
  min-height: 100%;
}
.page-wrap--fill {
  height: 100%;
  overflow: hidden;
}
</style>
