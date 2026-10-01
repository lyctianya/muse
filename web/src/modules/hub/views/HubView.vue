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
      <a-radio-group v-model="mode" type="button" size="small" @change="onModeChange" class="hub-modes">
        <a-radio value="drive">🚗 开车</a-radio>
        <a-radio value="orbit">🔭 漫游</a-radio>
      </a-radio-group>
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
      {{ mode === 'drive'
        ? 'WASD / 方向键开车 · Shift 加速 · 空格刹车 · R 回起点 · 靠近建筑自动弹出'
        : '拖拽旋转 · 滚轮缩放 · 点击建筑进入对应模块' }}
    </div>

    <!-- 开车模式：重置位置 -->
    <a-button v-if="!fallback && mode === 'drive'" class="hub-respawn" size="small" @click="hub && hub.respawn()">
      <template #icon><icon-refresh /></template>回起点
    </a-button>

    <!-- 触屏摇杆（开车模式） -->
    <div v-if="!fallback && mode === 'drive' && isTouch" ref="joyBase" class="hub-joy" @pointerdown="joyDown" @pointermove="joyMove" @pointerup="joyUp" @pointercancel="joyUp">
      <div class="hub-joy-knob" :style="joyStyle" />
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
import { IconUser, IconRefresh } from '@arco-design/web-vue/es/icon'

const router = useRouter()
const stage = ref(null)
const loading = ref(true)
const fallback = ref(false)
const selected = ref(null)
const mode = ref('drive')
const isTouch = 'ontouchstart' in window
const joyBase = ref(null)
const joyStyle = ref({})
let hub = null
let joyId = null

const today = computed(() => fmtDateLocal(new Date()))
const visibleModules = computed(() => MODULES.filter((m) => hasPerm(m.perm)))

function onModeChange(v) {
  selected.value = null
  hub && hub.setMode(v)
}

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
  if (hub && mode.value === 'orbit') hub.resetView()
}

/* 触屏摇杆 */
function joySet(e) {
  const el = joyBase.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2
  let dx = e.clientX - cx, dy = e.clientY - cy
  const max = r.width / 2 - 14
  const len = Math.hypot(dx, dy)
  if (len > max) { dx = dx / len * max; dy = dy / len * max }
  joyStyle.value = { transform: `translate(${dx}px, ${dy}px)` }
  if (hub) {
    hub.input.joySteer = dx / max
    hub.input.joyThrottle = -dy / max
  }
}
function joyDown(e) {
  joyId = e.pointerId
  e.currentTarget.setPointerCapture(e.pointerId)
  joySet(e)
}
function joyMove(e) {
  if (e.pointerId !== joyId) return
  joySet(e)
}
function joyUp(e) {
  if (e.pointerId !== joyId) return
  joyId = null
  joyStyle.value = {}
  if (hub) { hub.input.joySteer = 0; hub.input.joyThrottle = 0 }
}

onMounted(async () => {
  if (!authState.loaded) await loadUser()
  try {
    hub = await createHub(stage.value, {
      modules: visibleModules.value,
      onSelect: (mod) => {
        selected.value = mod
        if (mode.value === 'orbit') hub.focusTo(mod.id)
      },
      onDeselect: () => { selected.value = null },
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
.hub-modes { background: rgba(255,255,255,0.85); border-radius: 8px; padding: 2px; }
.hub-respawn {
  position: absolute; bottom: 22px; right: 20px; z-index: 10;
  background: rgba(255,255,255,0.9); border: 1px solid #d3a24a;
}
.hub-joy {
  position: absolute; bottom: 70px; left: 24px; z-index: 10;
  width: 120px; height: 120px; border-radius: 50%;
  background: rgba(26,35,64,0.25); border: 2px solid rgba(255,255,255,0.6);
  touch-action: none;
}
.hub-joy-knob {
  position: absolute; left: 50%; top: 50%;
  width: 52px; height: 52px; margin: -26px 0 0 -26px; border-radius: 50%;
  background: rgba(255,255,255,0.9); border: 2px solid #d3a24a;
}
</style>
