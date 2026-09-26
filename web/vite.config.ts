import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 本地开发：npm run dev 时把 /api 代理到本机 FastAPI（默认 8000 端口）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
