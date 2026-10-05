/** Muse business portal definitions (no Three.js) */
export const MUSE_AVENUE = {
  // Single roadside row near landing approach (Y-up Three space)
  origin: [29, 0, 33],
  spacing: 5.4,
  // Sign faces toward -Z (player approaching from lower Z)
  facing: Math.PI,
  // Themed props sit on the +X side of each post relative to facing
  propSide: 1,
}

export const MUSE_PORTALS = [
  { id: 'stock', title: '股票', route: '/market', perm: 'market:view', theme: 'stock', accent: '#2f6fed' },
  { id: 'blog', title: '博客', route: '/blog', perm: 'blog:view', theme: 'blog', accent: '#2f9e5a' },
  { id: 'gallery', title: '相册', route: '/gallery', perm: 'gallery:view', theme: 'gallery', accent: '#8b5cf6' },
  { id: 'game', title: '游戏', route: '/game', perm: 'game:view', theme: 'game', accent: '#d97706' },
  { id: 'tools', title: '工具', route: '/tools', perm: 'tools:use', theme: 'tools', accent: '#0e8a9a' },
  { id: 'files', title: '文件', route: '/files', perm: 'files:view', theme: 'files', accent: '#6b7280' },
  { id: 'sync', title: '数据更新', route: '/sync', perm: 'sync:view', theme: 'sync', accent: '#c2410c' },
  { id: 'users', title: '用户', route: '/users', perm: 'users:manage', theme: 'users', accent: '#be185d' },
]
