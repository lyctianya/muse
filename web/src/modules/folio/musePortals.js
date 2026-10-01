/** Muse business portal definitions (no Three.js) */
export const MUSE_PORTALS = [
  { id: 'stock', title: '股票', route: '/market', perm: 'market:view', position: [28, 0, 18], color: '#3b82f6' },
  { id: 'blog', title: '博客', route: '/blog', perm: 'blog:view', position: [36, 0, 18], color: '#22c55e' },
  { id: 'gallery', title: '相册', route: '/gallery', perm: 'gallery:view', position: [44, 0, 18], color: '#a855f7' },
  { id: 'game', title: '游戏', route: '/game', perm: 'game:view', position: [52, 0, 18], color: '#f59e0b' },
  { id: 'tools', title: '工具', route: '/tools', perm: 'tools:use', position: [28, 0, 28], color: '#06b6d4' },
  { id: 'files', title: '文件', route: '/files', perm: 'files:view', position: [36, 0, 28], color: '#64748b' },
  { id: 'sync', title: '数据更新', route: '/sync', perm: 'sync:view', position: [44, 0, 28], color: '#ef4444' },
  { id: 'users', title: '用户', route: '/users', perm: 'users:manage', position: [52, 0, 28], color: '#ec4899' },
]
