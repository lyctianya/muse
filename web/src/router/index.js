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
import LoginView from '../views/LoginView.vue'
import UsersView from '../views/UsersView.vue'
import { authState, hasPerm, loadUser } from '../utils/auth.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'home', component: HomeView, meta: { perm: 'market:view' } },
    { path: '/search', name: 'search', component: SearchView, meta: { perm: 'quotes:view' } },
    { path: '/chart/:market/:symbol', name: 'chart', component: ChartView, props: true, meta: { perm: 'quotes:view' } },
    { path: '/company/:symbol', name: 'company', component: CompanyView, props: true, meta: { perm: 'quotes:view' } },
    { path: '/weeks', name: 'weeks', component: WeeksView, meta: { perm: 'weeks:download' } },
    { path: '/extra', name: 'extra', component: MarketExtraView, meta: { perm: 'extra:view' } },
    { path: '/sync', name: 'sync', component: SyncView, meta: { perm: 'sync:view' } },
    { path: '/screener', name: 'screener', component: ScreenerView, meta: { perm: 'screener:use' } },
    { path: '/watchlist', name: 'watchlist', component: WatchlistView, meta: { perm: 'watchlist:use' } },
    { path: '/users', name: 'users', component: UsersView, meta: { perm: 'users:manage' } },
  ],
})

router.beforeEach(async (to) => {
  if (!authState.loaded) await loadUser()
  // 已登录访问 /login → 回首页
  if (to.name === 'login') {
    return authState.user ? '/' : true
  }
  // 未登录 → 登录页
  if (!authState.user) {
    return { path: '/login', query: { next: to.fullPath } }
  }
  // 无权限 → 首页（首页总是有 market:view 兜底；若连首页权限都没有则留空）
  const perm = to.meta?.perm
  if (perm && !hasPerm(perm)) {
    return hasPerm('market:view') ? '/' : true
  }
  return true
})

export default router
