import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import wasm from 'vite-plugin-wasm'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

// 本地开发：npm run dev 时把 /api 代理到本机 FastAPI（默认 8000 端口）
// host 固定 127.0.0.1：Windows 上 Vite 默认可能只绑 [::1]，导致浏览器访问 localhost/127.0.0.1 失败
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools({ launchEditor: 'cursor' }),
    wasm(),
    nodePolyfills(),
  ],
  build: {
    target: 'esnext',
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    exclude: ['@dimforge/rapier3d'],
  },
})
