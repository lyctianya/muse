import { createRouter, createWebHistory } from 'vue-router'
import SearchView from '../views/SearchView.vue'
import ChartView from '../views/ChartView.vue'
import WeeksView from '../views/WeeksView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'search', component: SearchView },
    { path: '/chart/:market/:symbol', name: 'chart', component: ChartView, props: true },
    { path: '/weeks', name: 'weeks', component: WeeksView },
  ],
})

export default router
