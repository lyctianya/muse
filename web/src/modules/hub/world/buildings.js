/* 8 栋主题建筑：程序化建模 + canvas 纹理细节 */
import { PALETTE } from './palette.js'
import { facadeTexture, pegboardTexture, paperTexture, hazardTexture, menuTexture } from './textures.js'

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

function plane(w, h, material, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), material)
  m.position.set(x, y, z)
  m.receiveShadow = true
  return m
}

/* K 线 canvas（红涨绿跌） */
function klineTexture() {
  const cv = document.createElement('canvas')
  cv.width = 512; cv.height = 288
  const ctx = cv.getContext('2d')
  ctx.fillStyle = '#1a2340'
  ctx.fillRect(0, 0, 512, 288)
  ctx.strokeStyle = 'rgba(255,255,255,0.08)'
  ctx.lineWidth = 1
  for (let i = 1; i < 6; i++) { ctx.beginPath(); ctx.moveTo(0, i * 48); ctx.lineTo(512, i * 48); ctx.stroke() }
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

/* 街机屏幕 */
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

/* 相框照片 */
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
    // 主楼：窗格立面
    const facade = await facadeTexture('#f5f5f0', 0.3)
    const tower = new THREE.Mesh(
      new THREE.BoxGeometry(3.6, 6, 3.6),
      new THREE.MeshStandardMaterial({ map: facade, roughness: 0.85 })
    )
    tower.position.set(0, 4, 0)
    tower.castShadow = tower.receiveShadow = true
    g.add(tower)
    for (let i = 0; i < 4; i++) g.add(box(3.7, 0.28, 3.7, PALETTE.goldDark, 0, 2.4 + i * 1.2, 0))
    g.add(box(3.9, 0.35, 3.9, PALETTE.goldDark, 0, 7.15, 0))
    // 入口：门 + 台阶 + 雨棚
    g.add(box(1.3, 2.1, 0.18, PALETTE.teal, 0, 1.55, 1.85))
    g.add(box(0.12, 0.12, 0.1, PALETTE.gold, 0.4, 1.5, 1.96))
    g.add(box(2.2, 0.25, 1.0, PALETTE.cream, 0, 0.62, 2.3))
    g.add(box(2.6, 0.25, 1.4, PALETTE.cream, 0, 0.32, 2.5))
    g.add(box(2.4, 0.14, 1.1, PALETTE.redDark, 0, 2.85, 2.2))
    g.add(box(0.14, 0.7, 0.14, PALETTE.dark, -1.05, 2.5, 2.2))
    g.add(box(0.14, 0.7, 0.14, PALETTE.dark, 1.05, 2.5, 2.2))
    // K 线牌
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(5.2, 2.9),
      new THREE.MeshBasicMaterial({ map: klineTexture(), side: THREE.DoubleSide })
    )
    board.position.set(0, 9.2, 0)
    board.rotation.x = -0.12
    g.add(board)
    g.add(box(5.4, 0.18, 0.18, PALETTE.goldDark, 0, 10.72, 0))
    g.add(box(0.25, 2.2, 0.25, PALETTE.dark, -2.2, 8, 0))
    g.add(box(0.25, 2.2, 0.25, PALETTE.dark, 2.2, 8, 0))
    g.userData.labelY = 11.6
    return g
  },

  /* 博客：报纸亭 */
  async blog() {
    await three()
    const g = new THREE.Group()
    g.add(box(3.2, 2.3, 2.6, PALETTE.teal, 0, 1.15, 0))
    // 百叶窗
    for (const wx of [-0.8, 0.8]) {
      g.add(box(0.9, 1.1, 0.1, PALETTE.tealLight, wx, 1.5, 1.32))
      for (let i = 0; i < 4; i++) g.add(box(0.9, 0.08, 0.12, PALETTE.dark, wx, 1.15 + i * 0.24, 1.32))
    }
    // 条纹雨棚
    const awnStart = g.children.length
    for (let i = 0; i < 6; i++) {
      g.add(box(0.62, 0.12, 3.0, i % 2 ? PALETTE.white : PALETTE.red, -1.55 + i * 0.62, 2.75, 0.35, { roughness: 0.6 }))
    }
    g.children.slice(awnStart).forEach((m) => { m.rotation.x = 0.28; m.position.z = 0.55; m.position.y = 2.72 })
    g.add(box(3.4, 0.18, 0.7, PALETTE.wood, 0, 1.15, 1.55))
    for (let i = 0; i < 3; i++) g.add(box(0.5, 0.09, 0.7, PALETTE.white, -0.9 + i * 0.85, 1.32, 1.55))
    // 菜单板
    const menu = plane(1.1, 0.85, new THREE.MeshBasicMaterial({ map: await menuTexture() }), -1.9, 1.7, 0.4)
    menu.rotation.y = 0.5
    g.add(menu)
    g.add(box(0.12, 1.0, 0.12, PALETTE.wood, -2.15, 0.9, 0.15))
    // 木箱
    g.add(box(0.7, 0.7, 0.7, PALETTE.wood, 2.1, 0.35, 0.6))
    g.add(box(0.55, 0.55, 0.55, PALETTE.wood, 2.05, 1.0, 0.55))
    // 招牌杆
    g.add(cyl(0.09, 0.09, 2.2, PALETTE.dark, 1.3, 3.3, -0.8))
    g.add(box(1.5, 0.7, 0.12, PALETTE.gold, 1.3, 4.35, -0.8))
    g.userData.labelY = 5.6
    return g
  },

  /* 相册：大相框 + 红毯 + 射灯 */
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
    const leg = box(0.3, 2.2, 0.3, PALETTE.wood, 0, 1.0, -0.9)
    leg.rotation.x = 0.5
    g.add(leg)
    // 红毯
    const carpet = plane(2.0, 6.5, mat(PALETTE.redDark, { roughness: 1 }), 0, 0.03, 3.6)
    carpet.rotation.x = -Math.PI / 2
    g.add(carpet)
    // 射灯
    for (const sx of [-2.6, 2.6]) {
      g.add(cyl(0.08, 0.1, 1.6, PALETTE.dark, sx, 0.8, 1.2))
      const lampHead = box(0.35, 0.3, 0.4, PALETTE.dark, sx, 1.75, 1.1)
      lampHead.rotation.x = -0.5
      g.add(lampHead)
      const glow = new THREE.Mesh(
        new THREE.PlaneGeometry(0.28, 0.22),
        new THREE.MeshBasicMaterial({ color: 0xfff4c2 })
      )
      glow.position.set(sx, 1.68, 1.28)
      glow.rotation.x = -0.5
      g.add(glow)
    }
    g.position.y = 0.4
    g.rotation.x = -0.06
    g.userData.labelY = 4.9
    return g
  },

  /* 游戏：街机柜（霓虹招牌 + 条纹） */
  async game() {
    await three()
    const g = new THREE.Group()
    g.add(box(2.0, 3.0, 1.6, PALETTE.red, 0, 1.5, 0))
    // 侧面条纹
    g.add(box(0.06, 2.6, 1.2, PALETTE.yellow, -1.02, 1.5, 0))
    g.add(box(0.06, 2.6, 1.2, PALETTE.yellow, 1.02, 1.5, 0))
    // 霓虹招牌
    const marquee = new THREE.Mesh(
      new THREE.BoxGeometry(2.0, 0.55, 1.6),
      new THREE.MeshStandardMaterial({ color: PALETTE.yellow, emissive: 0xffb300, emissiveIntensity: 0.55, roughness: 0.5 })
    )
    marquee.position.set(0, 3.25, 0)
    marquee.castShadow = true
    g.add(marquee)
    const scr = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 1.1),
      new THREE.MeshBasicMaterial({ map: arcadeTexture() })
    )
    scr.position.set(0, 2.35, 0.82)
    scr.rotation.x = -0.15
    g.add(scr)
    // 投币口
    g.add(box(0.3, 0.4, 0.06, PALETTE.dark, 0.6, 1.1, 0.82))
    g.add(box(0.2, 0.05, 0.02, PALETTE.gold, 0.6, 1.18, 0.86))
    // 操作台
    const panel = box(2.0, 0.18, 0.9, PALETTE.redDark, 0, 1.62, 0.95)
    panel.rotation.x = 0.25
    g.add(panel)
    g.add(cyl(0.05, 0.05, 0.35, PALETTE.dark, -0.4, 1.95, 1.0))
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 12), mat(PALETTE.gold))
    ball.position.set(-0.4, 2.16, 1.0); ball.castShadow = true
    g.add(ball)
    for (const bx of [-0.05, 0.35]) {
      g.add(cyl(0.11, 0.11, 0.08, bx < 0.2 ? PALETTE.tealLight : PALETTE.yellow, bx, 1.82, 1.05))
    }
    g.userData.labelY = 4.7
    return g
  },

  /* 工具箱：洞洞板工具墙 */
  async tools() {
    await three()
    const g = new THREE.Group()
    g.add(box(0.35, 2.6, 0.35, PALETTE.wood, -1.7, 1.3, 0))
    g.add(box(0.35, 2.6, 0.35, PALETTE.wood, 1.7, 1.3, 0))
    const peg = new THREE.Mesh(
      new THREE.BoxGeometry(4.0, 2.4, 0.22),
      new THREE.MeshStandardMaterial({ map: await pegboardTexture(), roughness: 0.9 })
    )
    peg.position.set(0, 2.0, 0)
    peg.castShadow = peg.receiveShadow = true
    g.add(peg)
    // 锤子
    g.add(cyl(0.07, 0.07, 1.1, PALETTE.trunk, -1.1, 2.0, 0.2))
    g.add(box(0.5, 0.28, 0.24, PALETTE.dark, -1.1, 2.6, 0.2))
    // 螺丝刀
    g.add(cyl(0.06, 0.06, 0.9, PALETTE.red, 0, 1.95, 0.2))
    g.add(cyl(0.02, 0.09, 0.35, PALETTE.cream, 0, 2.55, 0.2))
    // 扳手
    g.add(box(0.16, 1.0, 0.12, PALETTE.tealLight, 1.1, 1.95, 0.2))
    g.add(cyl(0.22, 0.22, 0.12, PALETTE.tealLight, 1.1, 2.55, 0.2))
    // 钉子排 + 卷尺
    for (let i = 0; i < 5; i++) g.add(box(0.1, 0.1, 0.14, PALETTE.goldDark, -1.5 + i * 0.75, 1.05, 0.16))
    g.add(box(0.35, 0.35, 0.18, PALETTE.yellow, 1.55, 1.15, 0.18))
    g.userData.labelY = 4.4
    return g
  },

  /* 文件：文件夹 + 横线纸 */
  async files() {
    await three()
    const g = new THREE.Group()
    g.add(box(3.4, 2.4, 0.22, PALETTE.yellow, 0, 1.5, -0.15))
    g.add(box(1.1, 0.4, 0.22, PALETTE.yellow, -1.0, 2.85, -0.15))
    g.add(box(3.4, 1.9, 0.18, 0xf7dc6f, 0, 1.2, 0.12))
    const paperMat = new THREE.MeshStandardMaterial({ map: await paperTexture(), roughness: 0.9 })
    for (let i = 0; i < 3; i++) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.1, 0.06), paperMat)
      p.position.set(-0.2 + i * 0.25, 2.5 + i * 0.12, -0.05 + i * 0.04)
      p.rotation.z = -0.06 * i
      p.castShadow = true
      g.add(p)
    }
    // 标签贴
    g.add(box(0.9, 0.35, 0.05, PALETTE.white, 0.8, 1.5, 0.24))
    g.add(box(0.6, 0.08, 0.02, PALETTE.red, 0.8, 1.5, 0.27))
    g.userData.labelY = 4.3
    return g
  },

  /* 数据更新：旋转齿轮 + 警示底座 */
  async sync() {
    await three()
    const g = new THREE.Group()
    g.add(cyl(1.3, 1.5, 0.7, PALETTE.cream, 0, 0.35, 0, 20))
    // 警示条纹环
    const hazard = new THREE.Mesh(
      new THREE.CylinderGeometry(1.52, 1.52, 0.22, 20, 1, true),
      new THREE.MeshStandardMaterial({ map: await hazardTexture(), roughness: 0.8 })
    )
    hazard.position.set(0, 0.62, 0)
    g.add(hazard)
    // 螺栓
    for (let i = 0; i < 4; i++) {
      const a = (i / 4) * Math.PI * 2 + Math.PI / 4
      g.add(cyl(0.12, 0.12, 0.12, PALETTE.dark, Math.cos(a) * 1.1, 0.76, Math.sin(a) * 1.1, 6))
    }
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
    g.userData.spin = gear
    g.userData.labelY = 4.2
    return g
  },

  /* 用户管理：小办公室 + 钥匙 + 烟囱 */
  async users() {
    await three()
    const g = new THREE.Group()
    g.add(box(3.4, 2.6, 3.0, PALETTE.white, 0, 1.3, 0))
    g.add(box(3.7, 0.3, 3.3, PALETTE.redDark, 0, 2.75, 0))
    // 发光窗
    const winMat = new THREE.MeshStandardMaterial({ color: 0x9fd3ef, emissive: 0xffd970, emissiveIntensity: 0.7, roughness: 0.2 })
    for (const wx of [-1.1, 1.1]) {
      const win = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.12), winMat)
      win.position.set(wx, 1.7, 1.52)
      g.add(win)
      g.add(box(1.0, 0.1, 0.14, PALETTE.cream, wx, 1.7, 1.52)) // 窗框十字
      g.add(box(0.1, 1.0, 0.14, PALETTE.cream, wx, 1.7, 1.52))
    }
    // 门 + 雨棚 + 门垫
    g.add(box(0.9, 1.7, 0.15, PALETTE.teal, 0, 0.85, 1.52))
    g.add(box(0.12, 0.12, 0.1, PALETTE.gold, 0.28, 0.85, 1.62))
    g.add(box(1.5, 0.12, 0.8, PALETTE.redDark, 0, 2.0, 1.8))
    const mat1 = plane(1.1, 0.6, mat(PALETTE.red, { roughness: 1 }), 0, 0.04, 2.3)
    mat1.rotation.x = -Math.PI / 2
    g.add(mat1)
    // 烟囱（烟雾粒子由主循环生成）
    g.add(box(0.5, 1.2, 0.5, PALETTE.cream, 1.0, 3.4, -0.6))
    g.add(box(0.66, 0.18, 0.66, PALETTE.redDark, 1.0, 4.05, -0.6))
    g.userData.chimney = new THREE.Vector3() // 世界坐标由主循环换算
    g.userData.chimneyLocal = { x: 1.0, y: 4.2, z: -0.6 }
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
    g.userData.labelY = 5.6
    return g
  },
}
