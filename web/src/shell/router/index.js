import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../../modules/stock/views/HomeView.vue'
import SearchView from '../../modules/stock/views/SearchView.vue'
import ChartView from '../../modules/stock/views/ChartView.vue'
import CompanyView from '../../modules/stock/views/CompanyView.vue'
import WeeksView from '../../modules/stock/views/WeeksView.vue'
import MarketExtraView from '../../modules/stock/views/MarketExtraView.vue'
import SyncView from '../../modules/stock/views/SyncView.vue'
import ScreenerView from '../../modules/stock/views/ScreenerView.vue'
import WatchlistView from '../../modules/stock/views/WatchlistView.vue'
import LoginView from '../views/LoginView.vue'
import UsersView from '../views/UsersView.vue'
import FilesView from '../../modules/files/views/FilesView.vue'
import BlogListView from '../../modules/blog/views/BlogListView.vue'
import BlogPostView from '../../modules/blog/views/BlogPostView.vue'
import BlogEditView from '../../modules/blog/views/BlogEditView.vue'
import GalleryView from '../../modules/gallery/views/GalleryView.vue'
import AlbumView from '../../modules/gallery/views/AlbumView.vue'
import GameView from '../../modules/game/views/GameView.vue'
import ToolsView from '../../modules/tools/views/ToolsView.vue'
import HubView from '../../modules/hub/views/HubView.vue'
import { authState, hasPerm, loadUser } from '../../platform/utils/auth.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'hub', component: HubView },
    { path: '/market', name: 'home', component: HomeView, meta: { perm: 'market:view' } },
    { path: '/search', name: 'search', component: SearchView, meta: { perm: 'quotes:view' } },
    { path: '/chart/:market/:symbol', name: 'chart', component: ChartView, props: true, meta: { perm: 'quotes:view' } },
    { path: '/company/:symbol', name: 'company', component: CompanyView, props: true, meta: { perm: 'quotes:view' } },
    { path: '/weeks', name: 'weeks', component: WeeksView, meta: { perm: 'weeks:download' } },
    { path: '/extra', name: 'extra', component: MarketExtraView, meta: { perm: 'extra:view' } },
    { path: '/sync', name: 'sync', component: SyncView, meta: { perm: 'sync:view' } },
    { path: '/screener', name: 'screener', component: ScreenerView, meta: { perm: 'screener:use' } },
    { path: '/watchlist', name: 'watchlist', component: WatchlistView, meta: { perm: 'watchlist:use' } },
    { path: '/users', name: 'users', component: UsersView, meta: { perm: 'users:manage' } },
    { path: '/files', name: 'files', component: FilesView, meta: { perm: 'files:view' } },
    { path: '/blog', name: 'blog', component: BlogListView, meta: { perm: 'blog:view' } },
    { path: '/blog/new', name: 'blog-new', component: BlogEditView, meta: { perm: 'blog:manage' } },
    { path: '/blog/edit/:id', name: 'blog-edit', component: BlogEditView, meta: { perm: 'blog:manage' } },
    { path: '/blog/:slug', name: 'blog-post', component: BlogPostView, meta: { perm: 'blog:view' } },
    { path: '/gallery', name: 'gallery', component: GalleryView, meta: { perm: 'gallery:view' } },
    { path: '/gallery/:id', name: 'album', component: AlbumView, meta: { perm: 'gallery:view' } },
    { path: '/game', name: 'game', component: GameView, meta: { perm: 'game:view' } },
    { path: '/tools', name: 'tools', component: ToolsView, meta: { perm: 'tools:use' } },
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
  // 无权限 → 3D 菜单（所有登录用户可进）
  const perm = to.meta?.perm
  if (perm && !hasPerm(perm)) {
    return '/'
  }
  return true
})

export default router
