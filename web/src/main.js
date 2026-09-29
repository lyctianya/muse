import { createApp } from 'vue'
import ArcoVue from '@arco-design/web-vue'
import '@arco-design/web-vue/dist/arco.css'
import './assets/theme.css'
import './utils/echarts-theme.js' // 注册 ECharts 全局主题（副作用）
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(ArcoVue)
app.use(router)
app.mount('#app')
