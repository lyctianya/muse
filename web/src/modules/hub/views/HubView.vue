<template>
  <div class="hub">
    <!-- 开场遮罩（点击后才初始化世界 + 解锁音频） -->
    <div v-if="!started && !fallback" class="hub-intro">
      <div class="hub-intro-card">
        <div class="hub-intro-logo">Muse</div>
        <div class="hub-intro-title">3D 世界</div>
        <p class="hub-intro-desc">开上小吉普，去逛逛你的数据王国吧</p>
        <a-button type="primary" size="large" shape="round" :loading="loading" @click="startWorld">
          进入世界 ▶
        </a-button>
        <p class="hub-intro-keys">WASD 开车 · 空格跳跃 · H 喇叭 · Shift 加速</p>
        <p class="hub-intro-credit">3D 素材 © 2025 Bruno Simon (MIT) · 音乐 Kounine (CC0)</p>
      </div>
    </div>
    <!-- 加载中 -->
    <div v-if="started && loading" class="hub-loading">
      <a-spin size="large" tip="正在建造 3D 世界…" />
    </div>
    <!-- WebGL 不可用时的回退 -->
    <div v-if="fallback" class="hub-fallback">
      <a-card title="3D 菜单不可用" style="width: 420px">
        <p v-if="fallbackReason === 'webgl'" style="color: #86909c">当前浏览器不支持 WebGL2，请使用下面的列表进入各模块：</p>
        <p v-else style="color: #86909c">3D 初始化失败（{{ fallbackReason }}），请使用下面的列表进入各模块：</p>
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
      <!-- 车漆切换（原站 VisualVehicle 6 种车漆） -->
      <a-dropdown v-if="started && !loading" @select="onPaintSelect">
        <a-button size="small" shape="round">🎨 {{ paintName }}</a-button>
        <template #content>
          <a-doption value="red">❤️ 红色</a-doption>
          <a-doption value="orange">🧡 橙色</a-doption>
          <a-doption value="white">🤍 白色</a-doption>
          <a-doption value="black">🖤 黑色</a-doption>
          <a-doption value="flames">🔥 火焰</a-doption>
          <a-doption value="abyssal">🌌 深渊</a-doption>
        </template>
      </a-dropdown>
      <!-- 天气/时间（原站 Weather/Lighting） -->
      <a-button v-if="started && !loading" size="small" shape="round" @click="onToggleRain">
        {{ raining ? '🌧️ 雨中' : '🌤️ 晴' }}
      </a-button>
      <!-- 季节（原站 Seasons） -->
      <a-dropdown v-if="started && !loading" @select="onSeasonSelect">
        <a-button size="small" shape="round">🍂 {{ seasonName }}</a-button>
        <template #content>
          <a-doption value="spring">🌸 春</a-doption>
          <a-doption value="summer">☀️ 夏</a-doption>
          <a-doption value="autumn">🍁 秋</a-doption>
          <a-doption value="winter">❄️ 冬</a-doption>
        </template>
      </a-dropdown>
      <div class="hub-user">
        <a-tag color="gold">{{ today }}</a-tag>
        <a-button size="small" shape="circle" :title="muted ? '取消静音' : '静音'" @click="onToggleMute">
          {{ muted ? '🔇' : '🔊' }}
        </a-button>
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
        ? 'WASD 开车 · 空格跳跃 · H 喇叭 · Shift 加速 · B 刹车 · R 回起点 · 靠近建筑自动弹出'
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

    <!-- 成就提示 -->
    <div class="hub-toasts">
      <div v-for="a in toasts" :key="a.id" class="hub-toast">
        <span class="hub-toast-icon">{{ a.icon }}</span>
        <div>
          <div class="hub-toast-title">🏆 {{ a.title }}</div>
          <div class="hub-toast-desc">{{ a.desc }}</div>
        </div>
      </div>
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
import { initAudio, toggleMute, isMuted } from '../world/audio.js'
import { authState, hasPerm, logout, loadUser } from '../../../platform/utils/auth.js'
import { fmtDateLocal } from '../../../platform/utils/date.js'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { IconUser, IconRefresh } from '@arco-design/web-vue/es/icon'

const router = useRouter()
const stage = ref(null)
const started = ref(false)
const loading = ref(false)
const fallback = ref(false)
const fallbackReason = ref('')
const selected = ref(null)
const mode = ref('drive')
const toasts = ref([])
const muted = ref(false)
const isTouch = 'ontouchstart' in window
const joyBase = ref(null)
const joyStyle = ref({})
let hub = null
let joyId = null

// 车漆（原站 6 种）
const paintName = ref('红色')
const PAINT_NAMES = { red: '红色', orange: '橙色', white: '白色', black: '黑色', flames: '火焰', abyssal: '深渊' }
function onPaintSelect(v) {
  if (hub && hub.setPaint(v)) {
    paintName.value = PAINT_NAMES[v] || v
  }
}

// 天气（原站 Weather）
const raining = ref(false)
function onToggleRain() {
  if (hub) {
    raining.value = !raining.value
    hub.setRain(raining.value)
  }
}

// 季节（原站 Seasons）
const seasonName = ref('夏')
const SEASON_NAMES = { spring: '春', summer: '夏', autumn: '秋', winter: '冬' }
function onSeasonSelect(v) {
  if (hub && hub.setSeason(v)) {
    seasonName.value = SEASON_NAMES[v] || v
  }
}

const today = computed(() => fmtDateLocal(new Date()))
const visibleModules = computed(() => MODULES.filter((m) => hasPerm(m.perm)))

function onModeChange(v) {
  selected.value = null
  hub && hub.setMode(v)
}

function onToggleMute() {
  muted.value = toggleMute()
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
})

async function startWorld() {
  started.value = true
  loading.value = true
  initAudio() // 用户手势内初始化音频
  // 先做真正的 WebGL2 能力探测，避免把其他失败误报成 WebGL 问题
  try {
    const probe = document.createElement('canvas')
    if (!probe.getContext('webgl2')) {
      fallback.value = true
      fallbackReason.value = 'webgl'
      loading.value = false
      return
    }
  } catch (e) { /* 忽略探测异常，交给 createHub 处理 */ }
  try {
    hub = await createHub(stage.value, {
      modules: visibleModules.value,
      onSelect: (mod) => {
        selected.value = mod
        if (mode.value === 'orbit') hub.focusTo(mod.id)
      },
      onDeselect: () => { selected.value = null },
      onAchievement: (a) => {
        toasts.value.push(a)
        setTimeout(() => { toasts.value = toasts.value.filter((x) => x.id !== a.id) }, 3500)
      },
    })
  } catch (e) {
    console.error('3D 初始化失败', e)
    fallback.value = true
    fallbackReason.value = (e && e.message) ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => {
  hub && hub.destroy()
  hub = null
})
</script>

<style scoped>
@font-face {
  font-family: 'Pally';
  src: url('/hub/fonts/Pally-Medium.woff2') format('woff2');
  font-weight: 500;
  font-display: swap;
}
@font-face {
  font-family: 'Pally';
  src: url('/hub/fonts/Pally-Bold.woff2') format('woff2');
  font-weight: 700;
  font-display: swap;
}
.hub { position: relative; width: 100%; height: 100vh; overflow: hidden; background: #9fd3ef; font-family: 'Pally', "PingFang SC", "Microsoft YaHei", sans-serif; }
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
.hub-intro {
  position: absolute; inset: 0; z-index: 30;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(160deg, #7fb8dd 0%, #a8d8f0 55%, #cfe8b8 100%);
}
.hub-intro-card { text-align: center; padding: 40px; }
.hub-intro-logo {
  display: inline-block; font-size: 44px; font-weight: 800; color: #1a2340;
  background: #fff; padding: 10px 28px; border-radius: 16px;
  border: 3px solid #d3a24a; box-shadow: 0 10px 30px rgba(26,35,64,0.2);
}
.hub-intro-title { font-size: 30px; font-weight: 700; color: #1a2340; margin-top: 18px; }
.hub-intro-desc { font-size: 15px; color: #3d4a6b; margin: 10px 0 24px; }
.hub-intro-keys { font-size: 12px; color: #5a6b7d; margin-top: 18px; }
.hub-intro-credit { font-size: 11px; color: #8a94a6; margin-top: 8px; }
.hub-toasts {
  position: absolute; left: 20px; bottom: 70px; z-index: 12;
  display: flex; flex-direction: column; gap: 10px;
}
.hub-toast {
  display: flex; align-items: center; gap: 12px;
  background: rgba(26,35,64,0.88); color: #fff;
  border: 1px solid #d3a24a; border-radius: 12px; padding: 10px 16px;
  animation: hub-toast-in 0.3s ease-out;
  max-width: 300px;
}
@keyframes hub-toast-in {
  from { transform: translateX(-30px); opacity: 0; }
  to { transform: none; opacity: 1; }
}
.hub-toast-icon { font-size: 26px; }
.hub-toast-title { font-size: 14px; font-weight: 700; color: #ffd970; }
.hub-toast-desc { font-size: 12px; color: #c9d1e0; }
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
