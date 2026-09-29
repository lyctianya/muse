<template>
  <a-card title="工具箱">
    <a-row :gutter="16">
      <a-col :span="6">
        <a-menu v-model:selected-keys="sel" @menu-item-click="(k) => (active = k)">
          <a-menu-item v-for="t in tools" :key="t.id">
            <template #icon><component :is="t.icon" /></template>
            {{ t.name }}
          </a-menu-item>
        </a-menu>
      </a-col>
      <a-col :span="18">
        <a-card :title="current.name" :bordered="false">
          <template #extra><span style="color: #86909c; font-size: 12px">{{ current.desc }}</span></template>
          <component :is="current.comp" />
        </a-card>
      </a-col>
    </a-row>
  </a-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  IconCode, IconClockCircle, IconExperiment, IconLink, IconSafe,
  IconQrcode, IconLock, IconBgColors, IconFindReplace, IconTag,
} from '@arco-design/web-vue/es/icon'
import JsonTool from '../tools/JsonTool.vue'
import TimestampTool from '../tools/TimestampTool.vue'
import Base64Tool from '../tools/Base64Tool.vue'
import UrlTool from '../tools/UrlTool.vue'
import HashTool from '../tools/HashTool.vue'
import QrTool from '../tools/QrTool.vue'
import PasswordTool from '../tools/PasswordTool.vue'
import ColorTool from '../tools/ColorTool.vue'
import RegexTool from '../tools/RegexTool.vue'
import UuidTool from '../tools/UuidTool.vue'

const tools = [
  { id: 'json', name: 'JSON 格式化', desc: '格式化 / 压缩 / 转义', icon: IconCode, comp: JsonTool },
  { id: 'timestamp', name: '时间戳转换', desc: 'Unix 时间戳 ↔ 日期', icon: IconClockCircle, comp: TimestampTool },
  { id: 'base64', name: 'Base64', desc: '编码 / 解码（支持中文）', icon: IconExperiment, comp: Base64Tool },
  { id: 'url', name: 'URL 编解码', desc: 'encodeURI / Component', icon: IconLink, comp: UrlTool },
  { id: 'hash', name: '哈希计算', desc: 'MD5 / SHA-1 / 256 / 512', icon: IconSafe, comp: HashTool },
  { id: 'qr', name: '二维码生成', desc: '文本 / 链接转二维码', icon: IconQrcode, comp: QrTool },
  { id: 'password', name: '密码生成器', desc: '随机强密码', icon: IconLock, comp: PasswordTool },
  { id: 'color', name: '颜色转换', desc: 'HEX / RGB / HSL 互转', icon: IconBgColors, comp: ColorTool },
  { id: 'regex', name: '正则测试', desc: '实时匹配高亮 + 捕获组', icon: IconFindReplace, comp: RegexTool },
  { id: 'uuid', name: 'UUID 生成', desc: '批量生成 v4', icon: IconTag, comp: UuidTool },
]
const active = ref('json')
const sel = ref(['json'])
const current = computed(() => tools.find((t) => t.id === active.value))
</script>
