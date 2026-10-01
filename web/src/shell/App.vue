<template>
  <a-layout style="min-height: 100vh" v-if="route.name !== 'login' && route.name !== 'hub'">
    <!-- 深色侧边栏 -->
    <a-layout-sider
      :width="224" :collapsed-width="64" collapsible v-model:collapsed="collapsed"
      style="background: linear-gradient(180deg, #1c2547 0%, #131a30 100%)"
      class="app-sider"
    >
      <div class="logo">
        <span class="logo-mark">◆</span>
        <span class="logo-text" v-show="!collapsed">股票数据管道</span>
      </div>
      <a-menu
        mode="vertical" theme="dark"
        :selected-keys="[activeKey]" :collapsed="collapsed"
        @menu-item-click="onMenuClick" class="side-menu"
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
        <a-menu-item v-if="can('tools:use')" key="tools"><template #icon><icon-tool /></template>工具箱</a-menu-item>
      </a-menu>
      <div class="sider-foot" v-show="!collapsed">
        <div class="foot-title">A股 · 港股 · 美股</div>
        <div class="foot-sub">日线（前复权）· 基本面</div>
      </div>
    </a-layout-sider>

    <a-layout>
      <!-- 顶栏：页面标题 + 用户 -->
      <a-layout-header class="app-header">
        <div class="page-title">{{ pageTitle }}</div>
        <div style="margin-left: auto; display: flex; align-items: center; gap: 12px">
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
        <div class="page-wrap">
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
  IconEdit, IconImage, IconTrophy, IconTool, IconCompass,
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
  blog: '博客', gallery: '相册', game: '游戏', tools: '工具箱',
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
    blog: '/blog', gallery: '/gallery', game: '/game', tools: '/tools',
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
.app-sider :deep(.arco-layout-sider-children) {
  display: flex; flex-direction: column; height: 100%;
}
.logo {
  display: flex; align-items: center; gap: 10px;
  height: 60px; padding: 0 20px; flex-shrink: 0;
}
.logo-mark { color: var(--gold); font-size: 18px; line-height: 1; }
.logo-text {
  color: #fff; font-size: 16px; font-weight: 700; letter-spacing: 0.06em;
  white-space: nowrap;
}
.side-menu { flex: 1; background: transparent !important; }
.side-menu :deep(.arco-menu-item) {
  color: rgba(255, 255, 255, 0.62) !important;
  margin: 2px 12px !important;
  border-radius: 8px !important;
  width: auto !important;
}
.side-menu :deep(.arco-menu-item:hover) {
  color: #fff !important; background: rgba(255, 255, 255, 0.07) !important;
}
.side-menu :deep(.arco-menu-selected) {
  color: #fff !important;
  background: linear-gradient(90deg, var(--gold-soft), transparent) !important;
  position: relative;
}
.side-menu :deep(.arco-menu-selected)::before {
  content: ""; position: absolute; left: -12px; top: 8px; bottom: 8px;
  width: 3px; border-radius: 2px; background: var(--gold);
}
.sider-foot {
  padding: 16px 20px; border-top: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}
.foot-title { color: rgba(255,255,255,0.75); font-size: 12px; font-weight: 600; }
.foot-sub { color: rgba(255,255,255,0.38); font-size: 11px; margin-top: 2px; }
.app-header {
  background: var(--card); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 24px; height: 56px !important;
  position: sticky; top: 0; z-index: 10;
}
.page-title { font-size: 17px; font-weight: 700; letter-spacing: 0.02em; }
.app-content { padding: 20px 24px 32px; background: var(--bg); min-height: calc(100vh - 56px); }
</style>
