<template>
  <div>
    <a-card :bordered="false">
      <template #title>自选股</template>
      <template #extra>
        <a-button type="primary" size="small" @click="load">
          <template #icon><icon-refresh /></template>刷新行情
        </a-button>
      </template>

      <a-empty v-if="!loading && groups.length === 0" description="还没有自选股票">
        <a-button type="primary" @click="$router.push('/search')">去搜索添加</a-button>
      </a-empty>

      <a-spin :loading="loading" style="width: 100%">
        <a-collapse v-if="groups.length" :default-active-key="groups.map(g => g.name)">
          <a-collapse-item v-for="g in groups" :key="g.name" :header="`${g.name}（${g.items.length}）`">
            <template #extra>
              <a-space @click.stop>
                <a-button type="text" size="mini" @click="openRename(g.name)">重命名</a-button>
                <a-popconfirm content="删除分组后，组内股票将移入「默认分组」，确定吗？"
                              @ok="deleteGroup(g.name)">
                  <a-button type="text" size="mini" status="danger">删除分组</a-button>
                </a-popconfirm>
              </a-space>
            </template>
            <a-table :data="g.items" :pagination="false" size="small" row-key="symbol" :bordered="true">
              <template #columns>
                <a-table-column title="代码" data-index="symbol" :width="90" />
                <a-table-column title="名称" :width="120">
                  <template #cell="{ record }">
                    <a-link @click="goCompany(record)">{{ record.name || '--' }}</a-link>
                  </template>
                </a-table-column>
                <a-table-column title="现价" :width="90">
                  <template #cell="{ record }">{{ fmt(record.close) }}</template>
                </a-table-column>
                <a-table-column title="涨跌幅%" :width="90">
                  <template #cell="{ record }">
                    <span :style="{ color: pcColor(record.pct_change) }">{{ fmtSigned(record.pct_change) }}</span>
                  </template>
                </a-table-column>
                <a-table-column title="总市值(亿)" :width="110">
                  <template #cell="{ record }">{{ fmt(record.total_mv_yi) }}</template>
                </a-table-column>
                <a-table-column title="市盈率TTM" :width="100">
                  <template #cell="{ record }">{{ fmt(record.pe_ttm) }}</template>
                </a-table-column>
                <a-table-column title="备注" data-index="note" :ellipsis="true" :tooltip="true" />
                <a-table-column title="操作" :width="230">
                  <template #cell="{ record }">
                    <a-space>
                      <a-button type="text" size="mini" @click="openMove(record)">改分组</a-button>
                      <a-button type="text" size="mini" @click="openNote(record)">改备注</a-button>
                      <a-popconfirm content="确定从自选中删除吗？" @ok="removeOne(record)">
                        <a-button type="text" size="mini" status="danger">删除</a-button>
                      </a-popconfirm>
                    </a-space>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </a-collapse-item>
        </a-collapse>
      </a-spin>
    </a-card>

    <!-- 改分组 -->
    <a-modal v-model:visible="moveVisible" title="修改分组" @ok="doMove" @cancel="moveVisible = false">
      <a-select v-model="moveGroup" allow-create placeholder="选择或输入新分组名" style="width: 100%">
        <a-option v-for="name in groupNames" :key="name" :value="name">{{ name }}</a-option>
      </a-select>
    </a-modal>

    <!-- 改备注 -->
    <a-modal v-model:visible="noteVisible" title="修改备注" @ok="doNote" @cancel="noteVisible = false">
      <a-textarea v-model="noteText" placeholder="备注" :max-length="200" show-word-limit :auto-size="{ minRows: 2 }" />
    </a-modal>

    <!-- 重命名分组 -->
    <a-modal v-model:visible="renameVisible" title="重命名分组" @ok="doRename" @cancel="renameVisible = false">
      <a-input v-model="renameText" placeholder="新分组名" :max-length="30" />
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'

const router = useRouter()
const loading = ref(false)
const items = ref([])

const groups = computed(() => {
  const map = new Map()
  for (const it of items.value) {
    const name = it.group_name || '默认分组'
    if (!map.has(name)) map.set(name, [])
    map.get(name).push(it)
  }
  return [...map.entries()].map(([name, list]) => ({ name, items: list }))
})
const groupNames = computed(() => groups.value.map((g) => g.name))

const fmt = (v) => (v === null || v === undefined ? '--' : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 }))
const fmtSigned = (v) => {
  if (v === null || v === undefined) return '--'
  const n = Number(v)
  return (n > 0 ? '+' : '') + n.toFixed(2)
}
const pcColor = (v) => (v > 0 ? '#f53f3f' : v < 0 ? '#00b42a' : undefined)

async function load() {
  loading.value = true
  try {
    const res = await fetch('/api/watchlist')
    if (!res.ok) throw new Error('加载失败')
    items.value = await res.json()
  } catch (e) {
    Message.error(e.message)
  } finally {
    loading.value = false
  }
}

function goCompany(record) {
  router.push({ path: `/company/${record.symbol}`, query: { name: record.name || '' } })
}

async function removeOne(record) {
  const q = new URLSearchParams({ market: record.market, symbol: record.symbol })
  const res = await fetch(`/api/watchlist?${q}`, { method: 'DELETE' })
  if (res.ok) { Message.success('已删除'); load() }
  else Message.error('删除失败')
}

// 改分组
const moveVisible = ref(false)
const moveGroup = ref('')
let moveTarget = null
function openMove(record) {
  moveTarget = record
  moveGroup.value = record.group_name
  moveVisible.value = true
}
async function doMove() {
  const name = (moveGroup.value || '').trim() || '默认分组'
  const res = await fetch('/api/watchlist', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ market: moveTarget.market, symbol: moveTarget.symbol, group_name: name }),
  })
  if (res.ok) { Message.success('已移动分组'); moveVisible.value = false; load() }
  else Message.error('操作失败')
}

// 改备注
const noteVisible = ref(false)
const noteText = ref('')
let noteTarget = null
function openNote(record) {
  noteTarget = record
  noteText.value = record.note || ''
  noteVisible.value = true
}
async function doNote() {
  const res = await fetch('/api/watchlist', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ market: noteTarget.market, symbol: noteTarget.symbol, note: noteText.value }),
  })
  if (res.ok) { Message.success('备注已更新'); noteVisible.value = false; load() }
  else Message.error('操作失败')
}

// 重命名分组
const renameVisible = ref(false)
const renameText = ref('')
let renameFrom = ''
function openRename(name) {
  renameFrom = name
  renameText.value = name
  renameVisible.value = true
}
async function doRename() {
  const to = (renameText.value || '').trim()
  if (!to || to === renameFrom) { renameVisible.value = false; return }
  const list = items.value.filter((it) => (it.group_name || '默认分组') === renameFrom)
  for (const it of list) {
    await fetch('/api/watchlist', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ market: it.market, symbol: it.symbol, group_name: to }),
    })
  }
  Message.success(`分组已重命名：${renameFrom} → ${to}`)
  renameVisible.value = false
  load()
}

// 删除分组：组内股票移入默认分组
async function deleteGroup(name) {
  if (name === '默认分组') { Message.warning('默认分组不能删除'); return }
  const list = items.value.filter((it) => (it.group_name || '默认分组') === name)
  for (const it of list) {
    await fetch('/api/watchlist', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ market: it.market, symbol: it.symbol, group_name: '默认分组' }),
    })
  }
  Message.success(`已删除分组「${name}」，${list.length} 只股票移入默认分组`)
  load()
}

onMounted(load)
</script>
