import { getJSON, postJSON } from '../../platform/utils/api.js'

/** 新闻60秒 API（后端前缀 /api/news60s） */
export const news60sApi = {
  getLatestNews: () => getJSON('/api/news60s/news/latest'),
  getNewsByDate: (date) => getJSON(`/api/news60s/news/${date}`),
  getNewsList: (params = {}) => {
    const q = new URLSearchParams()
    if (params.page) q.set('page', String(params.page))
    if (params.pageSize) q.set('page_size', String(params.pageSize))
    const qs = q.toString()
    return getJSON(`/api/news60s/news${qs ? `?${qs}` : ''}`)
  },
  syncNews: () => postJSON('/api/news60s/sync', {}),
  getSyncStats: () => getJSON('/api/news60s/stats'),
  testConnection: () => getJSON('/api/news60s/test'),
}
