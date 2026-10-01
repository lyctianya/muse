/* 8 栋主题建筑：纯代码低多边形，无外部模型 */
import { PALETTE } from './palette.js'

let THREE = null
async function three() {
  if (!THREE) THREE = await import('three')
  return THREE
}

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.05, ...opts })
}

function box(w, h, d, color, x = 0, y = 0, z = 0, opts = {}) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, opts))
  m.position.set(x, y, z)
  m.castShadow = true; m.receiveShadow = true
  return m
}

function cyl(rt, rb, h, color, x = 0, y = 0, z = 0, seg = 16) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat(color))
  m.position.set(x, y, z)
  m.castShadow = true; m.receiveShadow = true
  return m
}

/* K 线 canvas 纹理（红涨绿跌） */
function klineTexture() {
  const cv = document.createElement('canvas')
  cv.width = 512; cv.height = 288
  const ctx = cv.getContext('2d')
  ctx.fillStyle = '#1a2340'
  ctx.fillRect(0, 0, 512, 288)
  // 网格
  ctx.strokeStyle = 'rgba(255,255,255,0.08)'
  ctx.lineWidth = 1
  for (let i = 1; i < 6; i++) { ctx.beginPath(); ctx.moveTo(0, i * 48); ctx.lineTo(512, i * 48); ctx.stroke() }
  // K 线
  let price = 150
  const bw = 18, gap = 8
  for (let i = 0; i < 18; i++) {
    const o = price
    const c = o + (Math.random() - 0.45) * 36
    const h = Math.max(o, c) + Math.random() * 12
    const l = Math.min(o, c) - Math.random() * 12
    const x = 20 + i * (bw + gap)
    const y = (p) => 260 - (p - 60) * 1.1
    const up = c >= o
    ctx.strokeStyle = up ? '#e5484d' : '#18a058'
    ctx.fillStyle = up ? '#e5484d' : '#18a058'
    ctx.lineWidth = 3
    ctx.beginPath(); ctx.moveTo(x + bw / 2, y(h)); ctx.lineTo(x + bw / 2, y(l)); ctx.stroke()
    const top = y(Math.max(o, c)), bot = y(Math.min(o, c))
    ctx.fillRect(x, top, bw, Math.max(3, bot - top))
    price = c
  }
  // 均线
  ctx.strokeStyle = '#ffd970'
  ctx.lineWidth = 3
  ctx.beginPath()
  for (let i = 0; i < 18; i++) {
    const x = 20 + i * (bw + gap) + bw / 2
    const y = 150 - Math.sin(i * 0.7) * 40 + i * 2
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)
  }
  ctx.stroke()
  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

/* 街机屏幕 canvas */
function arcadeTexture() {
  const cv = document.createElement('canvas')
  cv.width = 256; cv.height = 192
  const ctx = cv.getContext('2d')
  ctx.fillStyle = '#0b1026'
  ctx.fillRect(0, 0, 256, 192)
  const cols = ['#e5484d', '#ffd970', '#18a058', '#4cc3ff', '#ee6c4d']
  for (let i = 0; i < 60; i++) {
    ctx.fillStyle = cols[i % cols.length]
    ctx.fillRect(Math.random() * 240, Math.random() * 176, 12, 12)
  }
  ctx.fillStyle = '#fff'
  ctx.font = '700 28px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('GAME', 128, 40)
  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

/* 相框照片 canvas */
function photoTexture() {
  const cv = document.createElement('canvas')
  cv.width = 256; cv.height = 192
  const ctx = cv.getContext('2d')
  const g = ctx.createLinearGradient(0, 0, 0, 192)
  g.addColorStop(0, '#9fd3ef'); g.addColorStop(0.65, '#f4d35e'); g.addColorStop(1, '#ee6c4d')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 256, 192)
  ctx.fillStyle = '#fff4c2'
  ctx.beginPath(); ctx.arc(190, 60, 26, 0, 7); ctx.fill()
  ctx.fillStyle = '#4e9e57'
  ctx.beginPath(); ctx.moveTo(0, 192); ctx.lineTo(90, 110); ctx.lineTo(170, 192); ctx.fill()
  ctx.beginPath(); ctx.moveTo(110, 192); ctx.lineTo(200, 120); ctx.lineTo(256, 192); ctx.fill()
  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

export const BUILDERS = {
  /* 股票：交易所大楼 + K 线广告牌 */
  async stock() {
    await three()
    const g = new THREE.Group()
    g.add(box(5, 1, 5, PALETTE.cream, 0, 0.5, 0))
    g.add(box(3.6, 6, 3.6, PALETTE.white, 0, 4, 0))
    for (let i = 0; i < 4; i++) g.add(box(3.7, 0.28, 3.7, PALETTE.goldDark, 0, 2.4 + i * 1.2, 0))
    g.add(box(3.9, 0.35, 3.9, PALETTE.goldDark, 0, 7.15, 0))
    // K 线牌
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(5.2, 2.9),
      new THREE.MeshBasicMaterial({ map: klineTexture(), side: THREE.DoubleSide })
    )
    board.position.set(0, 9.2, 0)
    board.rotation.x = -0.12
    g.add(board)
    g.add(box(0.25, 2.2, 0.25, PALETTE.dark, -2.2, 8, 0))
    g.add(box(0.25, 2.2, 0.25, PALETTE.dark, 2.2, 8, 0))
    g.userData.labelY = 11.4
    return g
  },

  /* 博客：报纸亭 */
  async blog() {
    await three()
    const g = new THREE.Group()
    g.add(box(3.2, 2.3, 2.6, PALETTE.teal, 0, 1.15, 0))
    // 条纹雨棚
    const awnStart = g.children.length
    for (let i = 0; i < 6; i++) {
      g.add(box(0.62, 0.12, 3.0, i % 2 ? PALETTE.white : PALETTE.red, -1.55 + i * 0.62, 2.75, 0.35, { roughness: 0.6 }))
    }
    g.children.slice(awnStart).forEach((m) => { m.rotation.x = 0.28; m.position.z = 0.55; m.position.y = 2.72 })
    g.add(box(3.4, 0.18, 0.7, PALETTE.wood, 0, 1.15, 1.55))
    // 报纸叠
    for (let i = 0; i < 3; i++) g.add(box(0.5, 0.09, 0.7, PALETTE.white, -0.9 + i * 0.85, 1.32, 1.55))
    // 招牌杆
    g.add(cyl(0.09, 0.09, 2.2, PALETTE.dark, 1.3, 3.3, -0.8))
    const sign = box(1.5, 0.7, 0.12, PALETTE.gold, 1.3, 4.35, -0.8)
    g.add(sign)
    g.userData.labelY = 5.6
    return g
  },

  /* 相册：大相框 */
  async gallery() {
    await three()
    const g = new THREE.Group()
    const fw = 4.2, fh = 3.0, t = 0.35
    g.add(box(fw, t, 0.3, PALETTE.gold, 0, fh - t / 2, 0))
    g.add(box(fw, t, 0.3, PALETTE.gold, 0, t / 2, 0))
    g.add(box(t, fh, 0.3, PALETTE.gold, -fw / 2 + t / 2, fh / 2, 0))
    g.add(box(t, fh, 0.3, PALETTE.gold, fw / 2 - t / 2, fh / 2, 0))
    const photo = new THREE.Mesh(
      new THREE.PlaneGeometry(fw - t * 1.4, fh - t * 1.4),
      new THREE.MeshBasicMaterial({ map: photoTexture() })
    )
    photo.position.set(0, fh / 2, 0.02)
    g.add(photo)
    // 支腿
    const leg = box(0.3, 2.2, 0.3, PALETTE.wood, 0, 1.0, -0.9)
    leg.rotation.x = 0.5
    g.add(leg)
    g.position.y = 0.4
    g.rotation.x = -0.06
    g.userData.labelY = 4.6
    return g
  },

  /* 游戏：街机柜 */
  async game() {
    await three()
    const g = new THREE.Group()
    g.add(box(2.0, 3.0, 1.6, PALETTE.red, 0, 1.5, 0))
    g.add(box(2.0, 0.55, 1.6, PALETTE.yellow, 0, 3.25, 0))
    const scr = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 1.1),
      new THREE.MeshBasicMaterial({ map: arcadeTexture() })
    )
    scr.position.set(0, 2.35, 0.82)
    scr.rotation.x = -0.15
    g.add(scr)
    g.userData.screen = scr
    // 操作台
    const panel = box(2.0, 0.18, 0.9, PALETTE.redDark, 0, 1.62, 0.95)
    panel.rotation.x = 0.25
    g.add(panel)
    g.add(cyl(0.05, 0.05, 0.35, PALETTE.dark, -0.4, 1.95, 1.0))
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 12), mat(PALETTE.gold))
    ball.position.set(-0.4, 2.16, 1.0); ball.castShadow = true
    g.add(ball)
    for (const bx of [-0.05, 0.35]) {
      const btn = cyl(0.11, 0.11, 0.08, bx < 0.2 ? PALETTE.tealLight : PALETTE.yellow, bx, 1.82, 1.05)
      g.add(btn)
    }
    g.userData.labelY = 4.6
    return g
  },

  /* 工具箱：工具墙 */
  async tools() {
    await three()
    const g = new THREE.Group()
    g.add(box(0.35, 2.6, 0.35, PALETTE.wood, -1.7, 1.3, 0))
    g.add(box(0.35, 2.6, 0.35, PALETTE.wood, 1.7, 1.3, 0))
    g.add(box(4.0, 2.4, 0.22, PALETTE.wood, 0, 2.0, 0))
    // 锤子
    g.add(cyl(0.07, 0.07, 1.1, PALETTE.trunk, -1.1, 2.0, 0.2))
    g.add(box(0.5, 0.28, 0.24, PALETTE.dark, -1.1, 2.6, 0.2))
    // 螺丝刀
    g.add(cyl(0.06, 0.06, 0.9, PALETTE.red, 0, 1.95, 0.2))
    g.add(cyl(0.02, 0.09, 0.35, PALETTE.cream, 0, 2.55, 0.2))
    // 扳手（简化）
    g.add(box(0.16, 1.0, 0.12, PALETTE.tealLight, 1.1, 1.95, 0.2))
    g.add(cyl(0.22, 0.22, 0.12, PALETTE.tealLight, 1.1, 2.55, 0.2))
    // 钉子排
    for (let i = 0; i < 5; i++) g.add(box(0.1, 0.1, 0.14, PALETTE.goldDark, -1.5 + i * 0.75, 1.05, 0.16))
    g.userData.labelY = 4.4
    return g
  },

  /* 文件：文件夹 */
  async files() {
    await three()
    const g = new THREE.Group()
    g.add(box(3.4, 2.4, 0.22, PALETTE.yellow, 0, 1.5, -0.15))
    g.add(box(1.1, 0.4, 0.22, PALETTE.yellow, -1.0, 2.85, -0.15))
    g.add(box(3.4, 1.9, 0.18, 0xf7dc6f, 0, 1.2, 0.12))
    // 纸张
    for (let i = 0; i < 3; i++) {
      const p = box(2.6, 1.1, 0.06, PALETTE.white, -0.2 + i * 0.25, 2.5 + i * 0.12, -0.05 + i * 0.04)
      p.rotation.z = -0.06 * i
      g.add(p)
    }
    g.userData.labelY = 4.3
    return g
  },

  /* 数据更新：旋转齿轮 */
  async sync() {
    await three()
    const g = new THREE.Group()
    g.add(cyl(1.3, 1.5, 0.7, PALETTE.cream, 0, 0.35, 0, 20))
    const gear = new THREE.Group()
    gear.add(cyl(1.15, 1.15, 0.45, PALETTE.tealLight, 0, 0, 0, 16))
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2
      const tooth = box(0.42, 0.45, 0.42, PALETTE.tealLight, Math.cos(a) * 1.32, Math.sin(a) * 1.32, 0)
      tooth.rotation.z = -a
      gear.add(tooth)
    }
    gear.add(cyl(0.4, 0.4, 0.6, PALETTE.goldDark, 0, 0, 0, 12))
    gear.position.set(0, 2.1, 0)
    g.add(gear)
    g.userData.spin = gear // 世界主循环驱动旋转
    g.userData.labelY = 4.2
    return g
  },

  /* 用户管理：小办公室 + 钥匙 */
  async users() {
    await three()
    const g = new THREE.Group()
    g.add(box(3.4, 2.6, 3.0, PALETTE.white, 0, 1.3, 0))
    g.add(box(3.7, 0.3, 3.3, PALETTE.redDark, 0, 2.75, 0))
    g.add(box(0.9, 1.7, 0.15, PALETTE.teal, 0, 0.85, 1.52))
    for (const wx of [-1.1, 1.1]) g.add(box(0.9, 0.9, 0.12, PALETTE.glass, wx, 1.7, 1.52, { roughness: 0.2 }))
    // 钥匙
    const key = new THREE.Group()
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.13, 10, 24), mat(PALETTE.gold))
    ring.castShadow = true
    key.add(ring)
    key.add(cyl(0.1, 0.1, 0.9, PALETTE.gold, 0.55, -0.35, 0))
    key.add(box(0.28, 0.12, 0.12, PALETTE.gold, 0.95, -0.62, 0))
    key.add(box(0.28, 0.12, 0.12, PALETTE.gold, 0.95, -0.82, 0))
    key.position.set(0, 4.1, 0)
    g.add(key)
    g.userData.bob = key
    g.userData.labelY = 5.4
    return g
  },
}
