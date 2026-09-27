import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SearchView from '../views/SearchView.vue'
import ChartView from '../views/ChartView.vue'
import CompanyView from '../views/CompanyView.vue'
import WeeksView from '../views/WeeksView.vue'
import MarketExtraView from '../views/MarketExtraView.vue'
import SyncView from '../views/SyncView.vue'
import ScreenerView from '../views/ScreenerView.vue'
import WatchlistView from '../views/WatchlistView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/search', name: 'search', component: SearchView },
    { path: '/chart/:market/:symbol', name: 'chart', component: ChartView, props: true },
    { path: '/company/:symbol', name: 'company', component: CompanyView, props: true },
    { path: '/weeks', name: 'weeks', component: WeeksView },
    { path: '/extra', name: 'extra', component: MarketExtraView },
    { path: '/sync', name: 'sync', component: SyncView },
    { path: '/screener', name: 'screener', component: ScreenerView },
    { path: '/watchlist', name: 'watchlist', component: WatchlistView },
  ],
})

export default router
