<template>
  <div>
    <a-row :gutter="16">
      <a-col :span="14">
        <a-card>
          <template #title><span class="section-title">用户列表</span></template>
          <template #extra>
            <a-button type="primary" size="small" @click="showCreate = true">新建用户</a-button>
          </template>
          <a-table :data="users" :pagination="false" size="small" :loading="loading">
            <template #columns>
              <a-table-column title="用户名" data-index="username" :width="130" />
              <a-table-column title="显示名" data-index="display_name" :width="120" />
              <a-table-column title="角色" :width="170">
                <template #cell="{ record }">
                  <a-space wrap>
                    <a-tag v-for="r in record.roles" :key="r" size="small"
                           :color="r === 'admin' ? 'red' : r === 'operator' ? 'arcoblue' : 'gray'">
                      {{ r }}
                    </a-tag>
                  </a-space>
                </template>
              </a-table-column>
              <a-table-column title="登录方式" :width="130">
                <template #cell="{ record }">
                  <a-space>
                    <a-tag v-if="record.has_password" size="small" color="arcoblue">密码</a-tag>
                    <a-tag v-if="record.has_google" size="small" color="green">Google</a-tag>
                  </a-space>
                </template>
              </a-table-column>
              <a-table-column title="状态" :width="90">
                <template #cell="{ record }">
                  <a-switch v-model="record.is_active" size="small"
                            @change="(v) => toggleActive(record, v)" />
                </template>
              </a-table-column>
              <a-table-column title="操作" :width="170">
                <template #cell="{ record }">
                  <a-space>
                    <a-link @click="openRoles(record)">角色</a-link>
                    <a-link @click="openReset(record)">改密码</a-link>
                  </a-space>
                </template>
              </a-table-column>
            </template>
          </a-table>
        </a-card>
      </a-col>
      <a-col :span="10">
        <a-card>
          <template #title><span class="section-title">角色权限</span></template>
          <div v-for="r in roles.roles" :key="r.name" class="role-block">
            <div class="role-head">
              <b>{{ r.name }}</b>
              <span class="muted">{{ r.description }}</span>
            </div>
            <a-checkbox-group v-model="rolePerms[r.name]" @change="() => saveRolePerms(r.name)">
              <a-checkbox v-for="p in roles.permissions" :key="p.key" :value="p.key">
                {{ p.description }}<span class="muted">（{{ p.key }}）</span>
              </a-checkbox>
            </a-checkbox-group>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 新建用户 -->
    <a-modal v-model:visible="showCreate" title="新建用户" @ok="doCreate" :ok-loading="saving">
      <a-form :model="newUser" layout="vertical">
        <a-form-item label="用户名"><a-input v-model="newUser.username" /></a-form-item>
        <a-form-item label="显示名"><a-input v-model="newUser.display_name" /></a-form-item>
        <a-form-item label="密码（留空则仅可 Google 登录）">
          <a-input-password v-model="newUser.password" />
        </a-form-item>
        <a-form-item label="角色">
          <a-checkbox-group v-model="newUser.roles">
            <a-checkbox v-for="r in roles.roles" :key="r.name" :value="r.name">{{ r.name }}</a-checkbox>
          </a-checkbox-group>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 改角色 -->
    <a-modal v-model:visible="showRoles" title="分配角色" @ok="doSaveRoles" :ok-loading="saving">
      <a-checkbox-group v-model="editRoles">
        <a-checkbox v-for="r in roles.roles" :key="r.name" :value="r.name">{{ r.name }}</a-checkbox>
      </a-checkbox-group>
    </a-modal>

    <!-- 改密码 -->
    <a-modal v-model:visible="showReset" title="重置密码" @ok="doReset" :ok-loading="saving">
      <a-input-password v-model="newPassword" placeholder="8 位以上，含字母和数字" />
    </a-modal>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getJSON, postJSON, putJSON } from '../utils/api.js'

const users = ref([])
const roles = ref({ roles: [], permissions: [], role_permissions: {} })
const rolePerms = ref({})
const loading = ref(false)
const saving = ref(false)
const showCreate = ref(false)
const showRoles = ref(false)
const showReset = ref(false)
const newUser = ref({ username: '', display_name: '', password: '', roles: ['viewer'] })
const editUser = ref(null)
const editRoles = ref([])
const newPassword = ref('')

async function load() {
  loading.value = true
  try {
    const [u, r] = await Promise.all([getJSON('/api/users'), getJSON('/api/roles')])
    users.value = u
    roles.value = r
    rolePerms.value = { ...r.role_permissions }
  } catch (e) {
    Message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function doCreate() {
  saving.value = true
  try {
    await postJSON('/api/users', newUser.value)
    Message.success('已创建')
    showCreate.value = false
    newUser.value = { username: '', display_name: '', password: '', roles: ['viewer'] }
    load()
  } catch (e) {
    Message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function toggleActive(record, v) {
  try {
    await putJSON(`/api/users/${record.id}`, { is_active: v })
  } catch (e) {
    Message.error(e.message)
    record.is_active = !v
  }
}

function openRoles(record) {
  editUser.value = record
  editRoles.value = [...record.roles]
  showRoles.value = true
}

async function doSaveRoles() {
  saving.value = true
  try {
    await putJSON(`/api/users/${editUser.value.id}`, { roles: editRoles.value })
    Message.success('已更新')
    showRoles.value = false
    load()
  } catch (e) {
    Message.error(e.message)
  } finally {
    saving.value = false
  }
}

function openReset(record) {
  editUser.value = record
  newPassword.value = ''
  showReset.value = true
}

async function doReset() {
  saving.value = true
  try {
    await putJSON(`/api/users/${editUser.value.id}`, { password: newPassword.value })
    Message.success('密码已重置')
    showReset.value = false
  } catch (e) {
    Message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function saveRolePerms(roleName) {
  try {
    await putJSON(`/api/roles/${roleName}/permissions`,
                  { permissions: rolePerms.value[roleName] || [] })
    Message.success(`${roleName} 权限已更新`)
  } catch (e) {
    Message.error(e.message)
    load()
  }
}

onMounted(load)
</script>

<style scoped>
.role-block { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.role-block:last-child { border-bottom: none; }
.role-head { margin-bottom: 8px; display: flex; gap: 8px; align-items: baseline; }
.role-block :deep(.arco-checkbox) { margin-right: 12px; margin-bottom: 6px; }
</style>
