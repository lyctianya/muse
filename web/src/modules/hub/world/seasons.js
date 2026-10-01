/* 季节：原站 Seasons 的 WebGL 实现
   - 春/夏/秋/冬切换树叶颜色
   - 春：粉绿，夏：深绿，秋：橙黄，冬：雪白（落叶减少） */
import * as THREE from 'three'

const SEASONS = {
  spring: {
    name: '春',
    birch: ['#ff8fb3', '#ffb3c9'],  // 粉
    oak: ['#8fd14f', '#b8e67a'],      // 嫩绿
    cherry: ['#ff6d6d', '#ff9990'],  // 粉（樱花）
    bush: ['#8fd14f', '#b8e67a'],
    grass: 0x7aa832,
    leaves: true,
  },
  summer: {
    name: '夏',
    birch: ['#ff4f2b', '#ff903f'],
    oak: ['#b4b536', '#d8cf3b'],
    cherry: ['#ff6d6d', '#ff9990'],
    bush: ['#b4b536', '#d8cf3b'],
    grass: 0x5a9a2a,
    leaves: true,
  },
  autumn: {
    name: '秋',
    birch: ['#ff8c1a', '#ffb84d'],   // 橙
    oak: ['#d4691a', '#e89a3c'],      // 橙黄
    cherry: ['#c43c1a', '#e86a3c'],   // 红橙
    bush: ['#d4691a', '#e89a3c'],
    grass: 0xa8a832,
    leaves: true, // 落叶更多
  },
  winter: {
    name: '冬',
    birch: ['#e8f0ff', '#ffffff'],   // 雪白
    oak: ['#d0d8e8', '#e8ecf5'],
    cherry: ['#d0d8e8', '#e8ecf5'],
    bush: ['#d0d8e8', '#e8ecf5'],
    grass: 0xd0d8c8, // 枯草
    leaves: false, // 无落叶
  },
}

export function createSeasons() {
  let current = 'summer'
  const listeners = []

  return {
    SEASONS,
    getCurrent: () => current,
    getConfig: () => SEASONS[current],
    setSeason(name) {
      if (!SEASONS[name]) return false
      current = name
      // 通知监听器（用于更新树叶材质）
      for (const fn of listeners) fn(SEASONS[name])
      return true
    },
    onChange(fn) {
      listeners.push(fn)
    },
  }
}
