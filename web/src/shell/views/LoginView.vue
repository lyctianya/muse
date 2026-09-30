<template>
  <div class="login-page">
    <a-card class="login-card" :bordered="false">
      <div class="login-logo"><span class="logo-mark">◆</span> 股票数据管道</div>
      <div class="login-sub">登录后使用 · 数据仅保存在本地</div>

      <a-tabs default-active-key="login" class="login-tabs">
        <a-tab-pane key="login" title="登录">
          <a-form :model="loginForm" layout="vertical" @submit="onLogin">
            <a-form-item label="用户名">
              <a-input v-model="loginForm.username" placeholder="用户名" allow-clear />
            </a-form-item>
            <a-form-item label="密码">
              <a-input-password v-model="loginForm.password" placeholder="密码" />
            </a-form-item>
            <a-button type="primary" long html-type="submit" :loading="loading">登录</a-button>
          </a-form>
        </a-tab-pane>
        <a-tab-pane key="register" title="注册">
          <a-form :model="regForm" layout="vertical" @submit="onRegister">
            <a-form-item label="用户名">
              <a-input v-model="regForm.username" placeholder="3-32 位字母/数字/下划线" allow-clear />
            </a-form-item>
            <a-form-item label="显示名">
              <a-input v-model="regForm.display_name" placeholder="选填，默认同用户名" allow-clear />
            </a-form-item>
            <a-form-item label="密码">
              <a-input-password v-model="regForm.password" placeholder="8 位以上，含字母和数字" />
            </a-form-item>
            <div class="muted" style="margin-bottom: 12px">注册默认获得只读（viewer）权限</div>
            <a-button type="primary" long html-type="submit" :loading="loading">注册并登录</a-button>
          </a-form>
        </a-tab-pane>
      </a-tabs>

      <a-divider>或</a-divider>
      <a-button long :loading="loading" @click="googleLogin">
        <template #icon><icon-google /></template>
        使用 Google 账号登录
      </a-button>
      <div v-if="error" class="login-error">{{ error }}</div>
    </a-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconGoogle } from '@arco-design/web-vue/es/icon'
import { postJSON } from '../../platform/utils/api.js'
import { loadUser } from '../../platform/utils/auth.js'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const error = ref('')
const loginForm = ref({ username: '', password: '' })
const regForm = ref({ username: '', password: '', display_name: '' })

function nextPath() {
  const n = route.query.next
  return typeof n === 'string' && n.startsWith('/') ? n : '/'
}

async function onLogin() {
  error.value = ''
  if (!loginForm.value.username || !loginForm.value.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    await postJSON('/api/auth/login', loginForm.value)
    await loadUser()
    router.replace(nextPath())
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function onRegister() {
  error.value = ''
  loading.value = true
  try {
    await postJSON('/api/auth/register', regForm.value)
    await loadUser()
    Message.success('注册成功')
    router.replace(nextPath())
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function googleLogin() {
  // 把前端源带给后端，OAuth 回调后跳回这里（而不是落在 8000）
  location.href = '/api/auth/google/login?next=' + encodeURIComponent(location.origin + '/')
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 56px);
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1c2547 0%, #2a3560 60%, #1c2547 100%);
  margin: -20px -24px -32px;
  padding: 40px 16px;
}
.login-card { width: 400px; max-width: 100%; border-radius: 16px; }
.login-logo {
  font-size: 20px; font-weight: 700; letter-spacing: 0.04em;
  display: flex; align-items: center; gap: 8px; justify-content: center;
}
.logo-mark { color: var(--gold); }
.login-sub { text-align: center; color: var(--text-3); font-size: 12px; margin: 6px 0 4px; }
.login-tabs { margin-top: 8px; }
.login-error { color: var(--rise); font-size: 13px; margin-top: 12px; text-align: center; }
</style>
