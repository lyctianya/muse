/* 认证状态：当前用户 + 权限 */
import { reactive } from 'vue'
import { getJSON, postJSON } from './api.js'

export const authState = reactive({ user: null, loaded: false })

export async function loadUser() {
  try {
    authState.user = await getJSON('/api/auth/me')
  } catch {
    authState.user = null
  }
  authState.loaded = true
  return authState.user
}

export function hasPerm(perm) {
  return !!authState.user?.permissions?.includes(perm)
}

export async function logout() {
  try {
    await postJSON('/api/auth/logout')
  } catch { /* ignore */ }
  authState.user = null
  location.href = '/login'
}
