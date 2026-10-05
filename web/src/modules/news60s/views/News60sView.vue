<template>
  <div class="news-60s">
    <div class="news-toolbar">
      <div class="toolbar-title">
        <span class="title-mark" />
        <h1>60秒新闻</h1>
      </div>
      <a-button type="outline" :loading="loading" @click="refreshNews">
        <template #icon><icon-refresh /></template>
        刷新
      </a-button>
    </div>

    <div v-if="loading && !newsData" class="state-card">
      <a-spin size="large" />
      <p>正在获取最新新闻...</p>
    </div>

    <div v-else-if="error" class="state-card error">
      <icon-exclamation-circle-fill />
      <h3>获取新闻失败</h3>
      <p>{{ error }}</p>
      <a-button type="primary" @click="refreshNews">重试</a-button>
    </div>

    <div v-else-if="newsData" class="news-stage">
      <a-button
        class="day-btn"
        shape="circle"
        size="large"
        :disabled="loading"
        title="前一天"
        @click="goToPreviousDay"
      >
        <icon-arrow-left />
      </a-button>

      <div class="news-scroll">
        <a-card class="meta-card" :bordered="true">
          <div class="meta-row">
            <icon-calendar />
            <span class="date">{{ newsData.date }}</span>
            <span v-if="newsData.day_of_week" class="meta-chip">{{ newsData.day_of_week }}</span>
            <span v-if="newsData.lunar_date" class="meta-chip muted">{{ newsData.lunar_date }}</span>
          </div>
          <div v-if="newsData.tip" class="daily-tip">
            <icon-bulb />
            <p>{{ newsData.tip }}</p>
          </div>
        </a-card>

        <a-card class="list-card" title="今日要闻">
          <template #extra>
            <span class="muted">点击条目可复制</span>
          </template>
          <div class="news-items">
            <button
              v-for="(item, index) in newsData.news"
              :key="index"
              type="button"
              class="news-item"
              @click="copyNewsItem(item)"
            >
              <span class="news-number">{{ index + 1 }}</span>
              <span class="news-text">{{ item }}</span>
              <span class="copy-hint"><icon-copy /></span>
            </button>
          </div>
        </a-card>
      </div>

      <a-button
        class="day-btn"
        shape="circle"
        size="large"
        :disabled="loading || isToday"
        title="后一天"
        @click="goToNextDay"
      >
        <icon-arrow-right />
      </a-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconArrowLeft,
  IconArrowRight,
  IconRefresh,
  IconCalendar,
  IconBulb,
  IconCopy,
  IconExclamationCircleFill,
} from '@arco-design/web-vue/es/icon'
import { news60sApi } from '../api.js'

const loading = ref(false)
const error = ref('')
const newsData = ref(null)
const currentDate = ref('')

const isToday = computed(() => {
  const today = new Date().toISOString().split('T')[0]
  return currentDate.value === today
})

const fetchNews = async (date) => {
  try {
    loading.value = true
    error.value = ''

    if (date) {
      newsData.value = await news60sApi.getNewsByDate(date)
      currentDate.value = date
    } else {
      newsData.value = await news60sApi.getLatestNews()
      currentDate.value = newsData.value.date
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取新闻失败'
    console.error('获取60秒新闻失败:', err)
  } finally {
    loading.value = false
  }
}

const refreshNews = async () => {
  await fetchNews(currentDate.value || undefined)
  if (!error.value) {
    Message.success('新闻已更新')
  }
}

const goToPreviousDay = async () => {
  if (loading.value) return
  const current = new Date(currentDate.value)
  current.setDate(current.getDate() - 1)
  await fetchNews(current.toISOString().split('T')[0])
}

const goToNextDay = async () => {
  if (loading.value || isToday.value) return
  const current = new Date(currentDate.value)
  current.setDate(current.getDate() + 1)
  await fetchNews(current.toISOString().split('T')[0])
}

const copyNewsItem = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    Message.success('已复制到剪贴板')
  } catch (err) {
    console.error('复制失败:', err)
    Message.error('复制失败')
  }
}

onMounted(() => {
  fetchNews()
})
</script>

<style scoped>
.news-60s {
  height: 100%;
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.news-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-shrink: 0;
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-mark {
  width: 4px;
  height: 18px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--gold), #b9862f);
}

.toolbar-title h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--text-1);
}

.news-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 48px;
  column-gap: 14px;
  align-items: stretch;
}

.day-btn {
  align-self: center;
  justify-self: center;
  background: var(--card) !important;
  border-color: var(--border) !important;
  box-shadow: var(--shadow-card);
  color: var(--text-2) !important;
}

.day-btn:hover:not(:disabled) {
  color: var(--gold) !important;
  border-color: var(--gold) !important;
}

.news-scroll {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 2px 4px 8px 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.news-scroll::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

.state-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  color: var(--text-2);
  text-align: center;
  padding: 32px;
}

.state-card.error :deep(svg) {
  font-size: 40px;
  color: var(--rise);
}

.state-card h3 {
  margin: 0;
  color: var(--text-1);
}

.meta-card {
  flex-shrink: 0;
}

.meta-card :deep(.arco-card-body) {
  padding: 20px 24px;
}

.meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-2);
}

.meta-row :deep(svg) {
  color: var(--gold);
}

.date {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-1);
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--gold-soft);
  color: #9a7428;
  font-size: 12px;
  font-weight: 600;
}

.meta-chip.muted {
  background: #f2f3f5;
  color: var(--text-3);
}

.daily-tip {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: #f7f8fa;
  border: 1px solid var(--border);
  color: var(--text-2);
  line-height: 1.65;
}

.daily-tip :deep(svg) {
  color: var(--gold);
  margin-top: 2px;
  flex-shrink: 0;
}

.daily-tip p {
  margin: 0;
}

.list-card :deep(.arco-card-header-title) {
  font-size: 15px;
}

.news-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.news-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  text-align: left;
  background: #f7f8fa;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  font: inherit;
  color: inherit;
}

.news-item:hover {
  background: #fff;
  border-color: rgba(211, 162, 74, 0.35);
  box-shadow: var(--shadow-card);
}

.news-number {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, var(--gold), #b9862f);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.news-text {
  flex: 1;
  color: var(--text-1);
  line-height: 1.65;
  font-size: 14px;
  padding-right: 24px;
}

.copy-hint {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-3);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.news-item:hover .copy-hint {
  opacity: 1;
  color: var(--gold);
}

.muted {
  color: var(--text-3);
  font-size: 12px;
}

@media (max-width: 768px) {
  .news-stage {
    grid-template-columns: 40px minmax(0, 1fr) 40px;
    column-gap: 8px;
  }

  .day-btn {
    width: 36px !important;
    height: 36px !important;
  }
}
</style>
