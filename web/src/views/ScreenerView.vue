<template>
  <div>
    <!-- 预设策略 -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="8" v-for="p in presets" :key="p.name">
        <a-card hoverable @click="applyPreset(p)" style="cursor: pointer">
          <template #title>{{ p.name }}</template>
          <div style="color: #86909c; font-size: 12px">{{ p.desc }}</div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 条件构造器 -->
    <a-card title="自定义条件" style="margin-bottom: 16px">
      <div v-for="(c, i) in conditions" :key="c.id"
           style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px">
        <a-select v-model="c.key" placeholder="选择字段" style="width: 180px"
                  @change="onFieldChange(c)">
          <a-option v-for="f in fields" :key="f.key" :value="f.key">
            {{ f.label }}<span v-if="f.unit">（{{ f.unit }}）</span>
          </a-option>
        </a-select>
        <a-select v-model="c.op" placeholder="运算符" style="width: 130px">
          <a-option v-for="op in opsOf(c)" :key="op" :value="op">
            {{ opLabels[op] }}
          </a-option>
        </a-select>
        <template v-if="c.op === 'between'">
          <a-input-number v-model="c.min" placeholder="最小值" style="width: 140px"
                          :precision="2" />
          <span style="color: #86909c">~</span>
          <a-input-number v-model="c.max" placeholder="最大值" style="width: 140px"
                          :precision="2" />
        </template>
        <a-input-number v-else v-model="c.value" placeholder="数值"
                        style="width: 200px" :precision="2" />
        <span v-if="unitOf(c)" style="color: #86909c; font-size: 12px">{{ unitOf(c) }}</span>
        <a-button type="text" status="danger" @click="removeCondition(i)">
          <template #icon><icon-delete /></template>
        </a-button>
      </div>
      <a-space style="margin-top: 8px">
        <a-button @click="addCondition">
          <template #icon><icon-plus /></template>添加条件
        </a-button>
        <a-button type="primary" :loading="loading" @click="runQuery">查询</a-button>
        <a-button @click="resetAll">重置</a-button>
      </a-space>
    </a-card>

    <!-- 结果 -->
    <a-card>
      <template #title>
        筛选结果
        <span v-if="searched" style="color: #86909c; font-weight: normal; font-size: 12px">
          （共 {{ total }} 只符合）
        </span>
      </template>
      <a-empty v-if="searched && rows.length === 0" description="没有符合条件的股票" />
      <a-table v-else-if="rows.length > 0" :data="rows" :pagination="{ pageSize: 50 }"
               size="small" row-key="symbol" :bordered="true"
               :row-class="() => 'clickable-row'" @row-click="goCompany">
        <template #columns>
          <a-table-column title="代码" data-index="symbol" :width="90" />
          <a-table-column title="名称" data-index="name" :width="110" />
          <a-table-column title="现价" :width="90">
            <template #cell="{ record }">{{ fmt(record.close) }}</template>
          </a-table-column>
          <a-table-column title="涨跌幅%" :width="90">
            <template #cell="{ record }">
              <span :style="{ color: record.pct_change > 0 ? '#f53f3f' : record.pct_change < 0 ? '#00b42a' : undefined }">
                {{ fmtSigned(record.pct_change) }}
              </span>
            </template>
          </a-table-column>
          <a-table-column title="总市值(亿)" :width="110">
            <template #cell="{ record }">{{ fmt(record.total_mv_yi) }}</template>
          </a-table-column>
          <a-table-column title="市盈率" :width="90">
            <template #cell="{ record }">{{ fmt(record.pe_ttm) }}</template>
          </a-table-column>
          <a-table-column title="连涨(天)" data-index="consec_up" :width="80" />
          <a-table-column title="连跌(天)" data-index="consec_down" :width="80" />
          <a-table-column title="周连涨(周)" data-index="week_up_streak" :width="90" />
          <a-table-column title="反弹60日%" :width="100">
            <template #cell="{ record }">{{ fmtSigned(record.rebound60) }}</template>
          </a-table-column>
        </template>
      </a-table>
      <a-empty v-else description="设置条件后点击查询" />
    </a-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'

const router = useRouter()
const fields = ref([])
const conditions = ref([])
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const searched = ref(false)
let seq = 0

const opLabels = { between: '介于', gt: '大于', lt: '小于', gte: '大于等于', lte: '小于等于' }

const presets = [
  {
    name: '小盘低估值',
    desc: '总市值 50~100 亿元，市盈率TTM < 100',
    filters: [
      { key: 'total_mv', op: 'between', min: 50, max: 100 },
      { key: 'pe_ttm', op: 'lt', value: 100 },
    ],
  },
  {
    name: '连跌一月',
    desc: '连跌天数 ≥ 20',
    filters: [{ key: 'consec_down', op: 'gte', value: 20 }],
  },
  {
    name: '周线强势反弹',
    desc: '周线连涨 ≥ 2 周，60日底部反弹 ≥ 10%',
    filters: [
      { key: 'week_up_streak', op: 'gte', value: 2 },
      { key: 'rebound60', op: 'gte', value: 10 },
    ],
  },
]

const fieldMap = computed(() => Object.fromEntries(fields.value.map(f => [f.key, f])))
const opsOf = (c) => fieldMap.value[c.key]?.ops || []
const unitOf = (c) => fieldMap.value[c.key]?.unit || ''

function newCondition(f) {
  return {
    id: ++seq, key: f.key, op: f.op,
    value: f.value ?? null, min: f.min ?? null, max: f.max ?? null,
  }
}

function onFieldChange(c) {
  const ops = opsOf(c)
  if (!ops.includes(c.op)) c.op = ops[0] || ''
}

function addCondition() {
  if (fields.value.length === 0) return
  const f = fields.value[0]
  conditions.value.push(newCondition({ key: f.key, op: f.ops[0] }))
}

function removeCondition(i) {
  conditions.value.splice(i, 1)
}

function applyPreset(p) {
  conditions.value = p.filters.map(f => newCondition(f))
  runQuery()
}

function resetAll() {
  conditions.value = []
  rows.value = []
  total.value = 0
  searched.value = false
}

function validate() {
  if (conditions.value.length === 0) {
    Message.warning('请至少添加一个条件')
    return false
  }
  for (const c of conditions.value) {
    if (!c.key || !c.op) {
      Message.warning('每行条件都必须选择字段和运算符')
      return false
    }
    const num = (v) => v !== null && v !== undefined && v !== '' && !isNaN(Number(v))
    if (c.op === 'between') {
      if (!num(c.min) || !num(c.max)) {
        Message.warning(`「${fieldMap.value[c.key]?.label}」介于需要填写最小值和最大值`)
        return false
      }
      if (Number(c.min) >= Number(c.max)) {
        Message.warning(`「${fieldMap.value[c.key]?.label}」最小值必须小于最大值`)
        return false
      }
    } else if (!num(c.value)) {
      Message.warning(`「${fieldMap.value[c.key]?.label}」需要填写数值`)
      return false
    }
  }
  return true
}

async function runQuery() {
  if (!validate()) return
  loading.value = true
  try {
    const filters = conditions.value.map(c => {
      const base = { key: c.key, op: c.op }
      if (c.op === 'between') {
        base.min = Number(c.min)
        base.max = Number(c.max)
      } else {
        base.value = Number(c.value)
      }
      return base
    })
    const res = await fetch('/api/screener/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filters, limit: 200 }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      Message.error(err.detail || `查询失败（${res.status}）`)
      return
    }
    const data = await res.json()
    rows.value = data.rows || []
    total.value = data.total || 0
    searched.value = true
  } catch (e) {
    Message.error('查询异常：' + e.message)
  } finally {
    loading.value = false
  }
}

function goCompany(record) {
  router.push(`/company/${record.symbol}`)
}

const fmt = (v) => (v === null || v === undefined ? '--' : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 }))
const fmtSigned = (v) => {
  if (v === null || v === undefined) return '--'
  const n = Number(v)
  return (n > 0 ? '+' : '') + n.toFixed(2)
}

onMounted(async () => {
  try {
    const res = await fetch('/api/screener/fields')
    fields.value = await res.json()
  } catch (e) {
    Message.error('字段元数据加载失败：' + e.message)
  }
})
</script>

<style scoped>
.clickable-row {
  cursor: pointer;
}
</style>
