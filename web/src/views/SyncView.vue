<template>
  <div>
    <!-- 运行中任务 -->
    <a-card v-if="runningJob" style="margin-bottom: 16px" :bordered="true">
      <template #title>
        <span><icon-sync spin style="margin-right: 6px" />同步任务运行中：{{ runningJob.table_name }}</span>
      </template>
      <div style="margin-bottom: 8px; color: #86909c; font-size: 12px">
        任务 {{ runningJob.job_id }} · 开始于 {{ runningJob.started_at }} · 日志每 3 秒刷新
      </div>
      <a-textarea :model-value="runningJob.log_tail || '等待日志输出…'" readonly
                  :auto-size="{ minRows: 8, maxRows: 16 }"
                  style="font-family: monospace; font-size: 12px" />
    </a-card>

    <a-card title="数据更新">
      <template #extra>
        <a-space>
          <span style="color: #86909c; font-size: 12px">
            状态以 sync_status 水位表为准；「重新扫描」才会对业务表做 COUNT/MAX
          </span>
          <a-button size="small" :loading="checking" @click="loadStatus">刷新状态</a-button>
          <a-button type="primary" size="small" :loading="scanning" @click="rescan">
            重新扫描
          </a-button>
        </a-space>
      </template>

      <a-alert v-if="anyWatermarkMissing" type="warning" style="margin-bottom: 16px"
               :closable="false">
        部分表尚无水位记录。请先点「重新扫描」从业务表初始化 sync_status。
      </a-alert>

      <div v-for="g in groups" :key="g" style="margin-bottom: 24px">
        <h3 style="margin: 0 0 12px">{{ g }} <span style="color: #86909c; font-weight: normal; font-size: 12px">（{{ byGroup[g].length }} 张表）</span></h3>
        <a-table :data="byGroup[g]" :pagination="false" size="small" row-key="key" :bordered="true">
          <template #columns>
            <a-table-column title="表名" data-index="key" :width="170" />
            <a-table-column title="说明" data-index="name" :width="130" />
            <a-table-column title="数据量" :width="120">
              <template #cell="{ record }">{{ record.rows.toLocaleString('zh-CN') }}</template>
            </a-table-column>
            <a-table-column title="最新日期" :width="120">
              <template #cell="{ record }">{{ record.latest_date || '--' }}</template>
            </a-table-column>
            <a-table-column title="上次同步" :width="170">
              <template #cell="{ record }">{{ record.last_synced_at || '--' }}</template>
            </a-table-column>
            <a-table-column title="状态" :width="130">
              <template #cell="{ record }">
                <a-tag v-if="record.watermark_missing" color="orangered">无水位</a-tag>
                <a-tag v-else-if="record.missing || record.rows === 0" color="red">无数据</a-tag>
                <a-tag v-else-if="record.needs_update" color="orange">需要更新</a-tag>
                <a-tag v-else color="green">数据最新</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="操作" :width="110">
              <template #cell="{ record }">
                <span v-if="!record.has_command" style="color: #c9cdd4">—</span>
                <a-button v-else type="text" size="mini"
                          :loading="updatingKey === record.key"
                          :disabled="!!runningJob || updatingKey !== ''"
                          @click="runUpdate(record)">
                  {{ runningJob ? '更新中' : '更新' }}
                </a-button>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </div>

      <!-- 历史任务 -->
      <h3 style="margin: 0 0 12px">历史任务</h3>
      <a-table :data="jobs" :pagination="false" size="small" row-key="job_id" :bordered="true"
               :expandable="expandable">
        <template #columns>
          <a-table-column title="任务" data-index="job_id" :width="100" />
          <a-table-column title="表" data-index="table_name" :width="130" />
          <a-table-column title="状态" :width="100">
            <template #cell="{ record }">
              <a-tag v-if="record.status === 'running'" color="blue">运行中</a-tag>
              <a-tag v-else-if="record.status === 'done'" color="green">完成</a-tag>
              <a-tag v-else color="red">失败</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="开始" data-index="started_at" :width="180" />
          <a-table-column title="结束" :width="180">
            <template #cell="{ record }">{{ record.finished_at || '--' }}</template>
          </a-table-column>
        </template>
        <template #expand-row="{ record }">
          <pre style="margin: 0; white-space: pre-wrap; font-size: 12px; max-height: 240px; overflow: auto">{{ record.log_tail || '（无日志）' }}</pre>
        </template>
      </a-table>
      <a-empty v-if="!jobs.length" description="暂无任务" style="margin-top: 12px" />
    </a-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'

const groups = ['行情', '基本面', '增量', '全量接口']
const status = ref([])
const jobs = ref([])
const checking = ref(false)
const scanning = ref(false)
const updatingKey = ref('')
const expandable = { title: '日志', width: 60 }

const byGroup = computed(() => {
  const m = {}
  for (const g of groups) m[g] = status.value.filter((t) => t.group === g)
  return m
})
const runningJob = computed(() => jobs.value.find((j) => j.status === 'running'))
const anyWatermarkMissing = computed(() =>
  status.value.some((t) => t.watermark_missing))

async function getJSON(url, opts) {
  const res = await fetch(url, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

async function loadStatus() {
  checking.value = true
  try {
    status.value = await getJSON('/api/sync/status')
  } catch (e) {
    Message.error(`状态检查失败：${e.message}`)
  } finally {
    checking.value = false
  }
}

async function rescan() {
  scanning.value = true
  try {
    const data = await getJSON('/api/sync/refresh-status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    status.value = data.status || []
    const n = (data.refreshed || []).filter((r) => r.ok).length
    Message.success(`已从业务表扫描 ${n} 张表并写入 sync_status`)
  } catch (e) {
    Message.error(`重新扫描失败：${e.message}`)
  } finally {
    scanning.value = false
  }
}

async function loadJobs() {
  try {
    jobs.value = await getJSON('/api/sync/jobs')
  } catch (e) {
    /* 忽略轮询错误 */
  }
}

async function runUpdate(record) {
  updatingKey.value = record.key
  try {
    const res = await fetch('/api/sync/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ table: record.key }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    const { job_id } = await res.json()
    Message.success(`已启动更新任务：${record.name}（${job_id}）`)
    await loadJobs()
  } catch (e) {
    Message.error(`启动失败：${e.message}`)
  } finally {
    updatingKey.value = ''
  }
}

// 任务结束（running 消失）时刷新表状态
watch(runningJob, (cur, prev) => {
  if (prev && !cur) loadStatus()
})

let timer = null
onMounted(() => {
  loadStatus()
  loadJobs()
  timer = setInterval(loadJobs, 3000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>
