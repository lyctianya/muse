<template>
  <div class="hub-folio">
    <div ref="host" class="hub-folio-host" />

    <div class="hub-folio-chrome">
      <div class="hub-folio-brand">Muse</div>
      <div class="hub-folio-actions">
        <template v-if="authState.user">
          <a-button size="small" type="primary" @click="$router.push('/market')">进入后台</a-button>
          <a-dropdown @select="onUserMenu">
            <a-button size="small">{{ authState.user.display_name }}</a-button>
            <template #content>
              <a-doption value="market">行情首页</a-doption>
              <a-doption value="logout">退出登录</a-doption>
            </template>
          </a-dropdown>
        </template>
        <a-button v-else size="small" type="primary" @click="goLogin">登录</a-button>
      </div>
    </div>

    <div v-if="error" class="hub-folio-error">
      <a-card title="3D 世界加载失败" style="width: 420px">
        <p style="color: #86909c; margin-bottom: 12px">{{ error }}</p>
        <a-list :data="fallbackModules" :bordered="false">
          <a-list-item v-for="m in fallbackModules" :key="m.id" style="cursor: pointer" @click="goModule(m)">
            {{ m.title }}
            <template #actions><a-link>进入</a-link></template>
          </a-list-item>
        </a-list>
      </a-card>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authState, hasPerm, logout } from '../../../platform/utils/auth.js'
import { MUSE_PORTALS } from '../../folio/musePortals.js'

const router = useRouter()
const host = ref(null)
const error = ref('')
let handle = null

const fallbackModules = MUSE_PORTALS.map((p) => ({
  id: p.id,
  title: p.title,
  route: p.route,
  perm: p.perm,
}))

function goLogin() {
  router.push({ path: '/login', query: { next: '/' } })
}

function goModule(m) {
  if (!authState.user) {
    router.push({ path: '/login', query: { next: m.route } })
    return
  }
  if (m.perm && !hasPerm(m.perm)) {
    error.value = `没有权限进入「${m.title}」`
    return
  }
  router.push(m.route)
}

function onNavigate(def) {
  if (!authState.user) {
    router.push({ path: '/login', query: { next: def.route } })
    return
  }
  if (def.perm && !hasPerm(def.perm)) {
    handle?.game?.notifications?.show(`没有权限进入「${def.title || def.route}」`, 'danger', 4)
    return
  }
  router.push(def.route)
}

async function onUserMenu(key) {
  if (key === 'market') router.push('/market')
  if (key === 'logout') {
    await logout()
    router.push('/')
  }
}

onMounted(async () => {
  try {
    const { mountFolio } = await import('../../folio/mount.js')
    handle = mountFolio(host.value, {
      onNavigate,
      getAuth: () => ({ user: authState.user, hasPerm }),
    })
  } catch (err) {
    console.error(err)
    error.value = err?.message || String(err)
  }
})

onBeforeUnmount(() => {
  handle?.destroy?.()
  handle = null
})
</script>

<style scoped>
.hub-folio {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: #1d1721;
}
.hub-folio-host {
  position: absolute;
  inset: 0;
}
.hub-folio-chrome {
  position: absolute;
  z-index: 40;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  pointer-events: none;
}
.hub-folio-brand {
  pointer-events: auto;
  font-family: 'Amatic SC', 'Nunito', cursive;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
  letter-spacing: 0.04em;
}
.hub-folio-actions {
  pointer-events: auto;
  display: flex;
  gap: 8px;
  align-items: center;
}
.hub-folio-error {
  position: absolute;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(29, 23, 33, 0.72);
}
</style>
