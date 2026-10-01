<template>
  <div class="hub">
    <!-- 加载中 -->
    <div v-if="loading" class="hub-loading">
      <a-spin size="large" tip="正在建造 3D 世界…" />
    </div>
    <!-- WebGL 不可用时的回退 -->
    <div v-if="fallback" class="hub-fallback">
      <a-card title="3D 菜单不可用" style="width: 420px">
        <p style="color: #86909c">当前浏览器不支持 WebGL，请使用下面的列表进入各模块：</p>
        <a-list :data="visibleModules" :bordered="false">
          <a-list-item v-for="m in visibleModules" :key="m.id" @click="$router.push(m.route)" style="cursor: pointer">
            {{ m.title }}<template #actions><a-link>进入</a-link></template>
          </a-list-item>
        </a-list>
      </a-card>
    </div>

    <div ref="stage" class="hub-stage" />

    <!-- 顶栏 -->
    <div v-if="!fallback" class="hub-top">
      <div class="hub-brand">
        <span class="hub-logo">Muse</span>
        <span class="hub-sub">3D 菜单</span>
      </div>
      <div class="hub-user">
        <a-tag color="gold">{{ today }}</a-tag>
        <a-dropdown v-if="authState.user" @select="onUserMenu">
          <a-button size="small">
            <template #icon><icon-user /></template>
            {{ authState.user.display_name }}
          </a-button>
          <template #content>
            <a-doption value="market">行情首页</a-doption>
            <a-doption value="logout">退出登录</a-doption>
          </template>
        </a-dropdown>
      </div>
    </div>

    <!-- 底部提示 -->
    <div v-if="!fallback && !selected" class="hub-hint">
      拖拽旋转 · 滚轮缩放 · 点击建筑进入对应模块
    </div>

    <!-- 选中模块卡片 -->
    <div v-if="selected" class="hub-card">
      <a-card :bordered="false">
        <div class="hub-card-title">{{ selected.title }}</div>
        <div class="hub-card-desc">{{ selected.desc }}</div>
        <a-space style="margin-top: 12px">
          <a-button type="primary" @click="enter">进入</a-button>
          <a-button @click="back">返回</a-button>
        </a-space>
      </a-card>
    </div>
  </div>
</template>

<script setup>
import { createHub, MODULES } from '../world/index.js'
import { authState, hasPerm, logout, loadUser } from '../../../platform/utils/auth.js'
import { fmtDateLocal } from '../../../platform/utils/date.js'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { IconUser } from '@arco-design/web-vue/es/icon'

const router = useRouter()
const stage = ref(null)
const loading = ref(true)
const fallback = ref(false)
const selected = ref(null)
let hub = null

const today = computed(() => fmtDateLocal(new Date()))
const visibleModules = computed(() => MODULES.filter((m) => hasPerm(m.perm)))

function onUserMenu(v) {
  if (v === 'logout') {
    logout()
    router.push('/login')
  } else if (v === 'market') {
    router.push('/market')
  }
}

function enter() {
  if (selected.value) router.push(selected.value.route)
}
function back() {
  selected.value = null
  hub && hub.resetView()
}

onMounted(async () => {
  if (!authState.loaded) await loadUser()
  try {
    hub = await createHub(stage.value, {
      modules: visibleModules.value,
      onSelect: (mod) => {
        selected.value = mod
        hub.focusTo(mod.id)
      },
    })
  } catch (e) {
    console.error('3D 初始化失败', e)
    fallback.value = true
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  hub && hub.destroy()
  hub = null
})
</script>

<style scoped>
.hub { position: relative; width: 100%; height: 100vh; overflow: hidden; background: #9fd3ef; }
.hub-stage { position: absolute; inset: 0; }
.hub-loading, .hub-fallback {
  position: absolute; inset: 0; z-index: 20;
  display: flex; align-items: center; justify-content: center;
  background: #9fd3ef;
}
.hub-top {
  position: absolute; top: 0; left: 0; right: 0; z-index: 10;
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; pointer-events: none;
}
.hub-top > * { pointer-events: auto; }
.hub-brand { display: flex; align-items: baseline; gap: 10px; }
.hub-logo {
  font-size: 22px; font-weight: 800; color: #1a2340;
  background: rgba(255,255,255,0.85); padding: 4px 14px; border-radius: 10px;
  border: 2px solid #d3a24a;
}
.hub-sub { font-size: 13px; color: #1a2340; background: rgba(255,255,255,0.7); padding: 3px 10px; border-radius: 8px; }
.hub-user { display: flex; align-items: center; gap: 10px; }
.hub-hint {
  position: absolute; bottom: 22px; left: 50%; transform: translateX(-50%); z-index: 10;
  background: rgba(26,35,64,0.75); color: #fff; font-size: 13px;
  padding: 8px 20px; border-radius: 20px; pointer-events: none;
  border: 1px solid rgba(211,162,74,0.6);
}
.hub-card {
  position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%); z-index: 11;
  width: 340px;
}
.hub-card :deep(.arco-card) { border-radius: 14px; border: 2px solid #d3a24a; box-shadow: 0 8px 30px rgba(26,35,64,0.25); }
.hub-card-title { font-size: 20px; font-weight: 700; color: #1a2340; }
.hub-card-desc { font-size: 13px; color: #86909c; margin-top: 4px; }
</style>
