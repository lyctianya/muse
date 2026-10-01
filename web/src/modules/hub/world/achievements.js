/* 成就系统：定义 + 进度追踪 */
export const ACHIEVEMENTS = [
  { id: 'first_drive', icon: '🚗', title: '初次上路', desc: '开动小吉普' },
  { id: 'first_jump', icon: '🚀', title: '一飞冲天', desc: '完成一次跳跃' },
  { id: 'crash', icon: '💥', title: '碰碰车', desc: '结结实实撞一次' },
  { id: 'speed', icon: '⚡', title: '极速狂飙', desc: '加速冲到 15 以上' },
  { id: 'honk', icon: '📯', title: '话痨司机', desc: '按 3 次喇叭' },
  { id: 'tourist', icon: '🗺️', title: '观光客', desc: '开车逛遍所有建筑' },
]

export function createTracker(onUnlock) {
  const got = new Set()
  const visited = new Set()
  let honks = 0
  function unlock(id) {
    if (got.has(id)) return
    got.add(id)
    const a = ACHIEVEMENTS.find((x) => x.id === id)
    if (a && onUnlock) onUnlock(a)
  }
  return {
    unlock,
    visit(id) { visited.add(id) },
    visitedCount() { return visited.size },
    honk() { honks++; if (honks >= 3) unlock('honk') },
    has(id) { return got.has(id) },
  }
}
