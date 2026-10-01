/* 3D 菜单世界：场景装配 + 轨道镜头 + 点击导航 */
import { PALETTE, MODULE_STYLE } from './palette.js'
import { makeLabel } from './labels.js'
import { buildJeep, createCar } from './car.js'
import { loadBrunoWorld, BUILDING_POS, WORLD_SPAWN, loadHeightGrid, groundHeightAt } from './brunoWorld.js'
import { createParticles } from './particles.js'
import { initAudio, engineUpdate, honk as honkSound, ding, boing, thud } from './audio.js'
import { createTracker } from './achievements.js'

export const MODULES = [
  { id: 'stock', title: '股票', desc: '市场概览 · 行情 · 选股', route: '/market', perm: 'market:view' },
  { id: 'blog', title: '博客', desc: '文章 · 随笔', route: '/blog', perm: 'blog:view' },
  { id: 'gallery', title: '相册', desc: '照片 · 回忆', route: '/gallery', perm: 'gallery:view' },
  { id: 'game', title: '游戏', desc: '星尘收集 · 排行榜', route: '/game', perm: 'game:view' },
  { id: 'tools', title: '工具箱', desc: '10 个 web 小工具', route: '/tools', perm: 'tools:use' },
  { id: 'files', title: '文件', desc: '文件管理', route: '/files', perm: 'files:view' },
  { id: 'sync', title: '数据更新', desc: '回填 · 同步状态', route: '/sync', perm: 'sync:view' },
  { id: 'users', title: '用户管理', desc: '用户 · 角色权限', route: '/users', perm: 'users:manage' },
]

const RADIUS = 16 // 保留：旧世界半径（现用原站世界坐标）

function cssColor(hex) {
  return '#' + hex.toString(16).padStart(6, '0')
}

/* 原站建筑碰撞体近似（中心 x,z / 半尺寸 hx,hz / 顶高 top，来自 areas.glb 烘焙坐标） */
const BUILDING_SOLIDS = {
  stock:   { x: 35.1,  z: 11.4,  hx: 5.5, hz: 4.5, top: 4.5 },
  blog:    { x: 25.9,  z: -1.4,  hx: 5.0, hz: 9.5, top: 3.0 },
  gallery: { x: 29.6,  z: -25.3, hx: 12.5, hz: 9.0, top: 5.5 },
  game:    { x: 6.0,   z: 66.1,  hx: 21.0, hz: 13.0, top: 7.5 },
  tools:   { x: 12.7,  z: 16.3,  hx: 4.8, hz: 4.0, top: 5.2 },
  files:   { x: 51.6,  z: -11.2, hx: 4.5, hz: 5.8, top: 4.0 },
  sync:    { x: 70.5,  z: 9.4,   hx: 5.5, hz: 6.5, top: 7.5 },
  users:   { x: 48.5,  z: 38.5,  hx: 11.0, hz: 10.0, top: 5.0 },
}

export async function createHub(container, hooks = {}) {
  const THREE = await import('three')

  const W = container.clientWidth || 800
  const H = container.clientHeight || 600

  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(W, H)
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(PALETTE.sky)
  scene.fog = new THREE.Fog(PALETTE.fog, 90, 260)

  const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 600)

  // 灯光
  scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x9aa86b, 0.95))
  const sun = new THREE.DirectionalLight(0xfff1d6, 1.7)
  sun.position.set(22, 30, 14)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  sun.shadow.camera.left = -45; sun.shadow.camera.right = 45
  sun.shadow.camera.top = 45; sun.shadow.camera.bottom = -45
  sun.shadow.camera.far = 120
  sun.shadow.bias = -0.0004
  scene.add(sun)

  /* ---------- 原站完整世界（地形/建筑/树木/灌木/花） ---------- */
  await loadBrunoWorld(scene)

  const modules = hooks.modules || MODULES

  // 等原站字体就绪再画标签
  try { await document.fonts.load('700 56px Pally') } catch (e) { /* fallback */ }

  // 模块交互点：放在原站建筑位置上空
  const pickables = []
  const zonePts = [] // 触发区：建筑位置
  const labels = []
  const hitZones = [] // 隐形点击柱
  for (const m of modules) {
    const bp = BUILDING_POS[m.id]
    if (!bp) continue
    const solid = BUILDING_SOLIDS[m.id] || { hx: 5, hz: 5, top: 5 }
    zonePts.push({ id: m.id, x: bp.x, z: bp.z })
    const accent = cssColor((MODULE_STYLE[m.id] || {}).accent || 0xd3a24a)
    const label = await makeLabel(m.title, accent)
    label.position.set(bp.x, solid.top + 3.2, bp.z)
    label.userData.moduleId = m.id
    scene.add(label)
    labels.push({ sp: label, baseY: label.position.y, phase: Math.random() * 6 })
    // 隐形点击柱（方便点选建筑）
    const hz = new THREE.Mesh(
      new THREE.CylinderGeometry(Math.max(solid.hx, solid.hz) * 0.9, Math.max(solid.hx, solid.hz) * 0.9, solid.top + 4, 8),
      new THREE.MeshBasicMaterial({ visible: false })
    )
    hz.position.set(bp.x, (solid.top + 4) / 2, bp.z)
    hz.userData.moduleId = m.id
    scene.add(hz)
    hitZones.push(hz)
    pickables.push(hz)
  }

  // 云
  const clouds = []
  for (let i = 0; i < 5; i++) {
    const cl = new THREE.Group()
    const n = 3 + Math.floor(Math.random() * 2)
    for (let j = 0; j < n; j++) {
      const s = new THREE.Mesh(
        new THREE.SphereGeometry(1.4 + Math.random() * 1.2, 12, 12),
        new THREE.MeshStandardMaterial({ color: PALETTE.cloud, roughness: 1 })
      )
      s.position.set(j * 1.8 - n * 0.9, Math.random() * 0.6, Math.random() * 1.2 - 0.6)
      cl.add(s)
    }
    cl.position.set(-90 + Math.random() * 180, 22 + Math.random() * 8, -90 + Math.random() * 180)
    scene.add(cl)
    clouds.push({ g: cl, v: 0.4 + Math.random() * 0.5 })
  }

  /* ---------- 粒子 + 成就 ---------- */
  const particles = await createParticles(scene)
  const tracker = createTracker((a) => {
    if (hooks.onAchievement) hooks.onAchievement(a)
    ding()
  })

  /* ---------- Rapier 物理 ---------- */
  const rapierMod = await import('@dimforge/rapier3d-compat')
  const RAPIER = rapierMod.default
  await RAPIER.init()
  const phys = new RAPIER.World({ x: 0, y: -9.81, z: 0 })
  phys.timestep = 1 / 60
  // 地形 trimesh 碰撞体（原站地形烘焙；heightfield 在此 rapier 版本 WASM trap，改用 trimesh）
  {
    const [vb, ib] = await Promise.all([
      fetch('/hub/world/terrain_verts.raw').then((r) => r.arrayBuffer()),
      fetch('/hub/world/terrain_idx.raw').then((r) => r.arrayBuffer()),
    ])
    const verts = new Float32Array(vb)
    const idx = new Uint32Array(ib)
    phys.createCollider(RAPIER.ColliderDesc.trimesh(verts, idx).setFriction(0.9))
  }
  // 建筑碰撞体（近似盒）
  for (const m of modules) {
    const s = BUILDING_SOLIDS[m.id]
    if (!s) continue
    phys.createCollider(
      RAPIER.ColliderDesc.cuboid(s.hx, s.top / 2, s.hz).setTranslation(s.x, s.top / 2, s.z).setFriction(0.4)
    )
  }

  /* ---------- 吉普车 ---------- */
  const jeep = await buildJeep()
  scene.add(jeep.carrier)
  const spawnY = groundHeightAt(WORLD_SPAWN.x, WORLD_SPAWN.z) + 0.7
  const car = createCar(RAPIER, phys, jeep, { x: WORLD_SPAWN.x, y: spawnY, z: WORLD_SPAWN.z, yaw: WORLD_SPAWN.yaw })
  let chaseDist = 10.5
  { // 开车模式初始机位
    const p = car.pos, yaw = car.yaw
    const fx = Math.sin(yaw), fz = Math.cos(yaw)
    camera.position.set(p.x - fx * chaseDist, 5.2, p.z - fz * chaseDist)
    camera.lookAt(p.x + fx * 4, 1.7, p.z + fz * 4)
  }

  /* ---------- 输入（键盘 + 摇杆） ---------- */
  const input = { throttle: 0, steer: 0, brake: false, boost: false, joyThrottle: 0, joySteer: 0, jump: false }
  const keys = new Set()
  const clamp01 = (v) => Math.max(-1, Math.min(1, v))
  let honkT = 0
  function doHonk() {
    honkSound()
    jeep.bubble.visible = true
    honkT = 0.9
    tracker.honk()
  }
  function onKeyDown(e) {
    const k = e.key.toLowerCase()
    if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' '].includes(k)) e.preventDefault()
    if (mode !== 'drive') { keys.add(k); return }
    if (k === 'r') car.respawn()
    if (k === ' ') input.jump = true
    if (k === 'h') doHonk()
    keys.add(k)
  }
  function onKeyUp(e) { keys.delete(e.key.toLowerCase()) }
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  function pollKeys() {
    const up = keys.has('w') || keys.has('arrowup')
    const down = keys.has('s') || keys.has('arrowdown')
    const left = keys.has('a') || keys.has('arrowleft')
    const right = keys.has('d') || keys.has('arrowright')
    input.throttle = clamp01((up ? 1 : 0) + (down ? -0.65 : 0) + input.joyThrottle)
    input.steer = clamp01((right ? 1 : 0) + (left ? -1 : 0) + input.joySteer)
    input.brake = keys.has('b') || keys.has('control')
    input.boost = keys.has('shift')
  }

  /* ---------- 模式：drive 开车 / orbit 漫游 ---------- */
  let mode = 'drive'
  let zoneId = null
  let manualLock = null
  function clearZone() {
    if (zoneId && hooks.onDeselect) hooks.onDeselect()
    zoneId = null
    manualLock = null
  }
  function nearestZone(p) {
    let best = null, bd = Infinity
    for (const z of zonePts) {
      const s = BUILDING_SOLIDS[z.id]
      const trig = s ? Math.max(s.hx, s.hz) + 5 : 8
      const dx = p.x - z.x, dz = p.z - z.z
      const d2 = dx * dx + dz * dz
      if (d2 < trig * trig && d2 < bd) { bd = d2; best = z.id }
    }
    return best
  }
  function checkZone() {
    const p = car.pos
    if (manualLock) {
      const moved = Math.hypot(p.x - manualLock.x, p.z - manualLock.z)
      const now = nearestZone(p)
      if (moved <= 2.5 && (!now || now === manualLock.id)) return // 保持手动选中
      manualLock = null
    }
    const best = nearestZone(p)
    if (best !== zoneId) {
      zoneId = best
      if (best) {
        const mod = modules.find((m) => m.id === best)
        tracker.visit(best)
        if (tracker.visitedCount() === modules.length) tracker.unlock('tourist')
        if (mod && hooks.onSelect) hooks.onSelect(mod)
      } else if (hooks.onDeselect) hooks.onDeselect()
    }
  }
  function setMode(m) {
    if (m === mode) return
    mode = m
    autoRotate = false
    clearZone()
    if (m === 'orbit') {
      // 以车为中心过渡到轨道镜头
      const p = car.pos
      orbit.goalTarget.set(p.x, 2.2, p.z)
      const off = camera.position.clone().sub(orbit.goalTarget)
      const len = Math.max(13, Math.min(48, off.length()))
      orbit.goalRadius = len
      orbit.goalTheta = Math.atan2(off.x, off.z)
      const cosPhi = Math.max(-1, Math.min(1, off.y / off.length()))
      orbit.goalPhi = Math.max(0.45, Math.min(1.35, Math.acos(cosPhi)))
    }
  }

  /* ---------- 镜头（手写轨道 + 阻尼） ---------- */
  const orbit = {
    target: new THREE.Vector3(0, 2.2, 0),
    radius: 30, theta: 0.7, phi: 1.02,
    goalTarget: new THREE.Vector3(0, 2.2, 0),
    goalRadius: 30, goalTheta: 0.7, goalPhi: 1.02,
  }
  let autoRotate = true
  let dragging = false
  let downX = 0, downY = 0, moved = 0
  let pinchD = 0

  function applyOrbit(dt) {
    const k = 1 - Math.exp(-6 * dt)
    orbit.target.lerp(orbit.goalTarget, k)
    orbit.radius += (orbit.goalRadius - orbit.radius) * k
    // theta 取最短路径插值
    let dTheta = orbit.goalTheta - orbit.theta
    dTheta = Math.atan2(Math.sin(dTheta), Math.cos(dTheta))
    orbit.theta += dTheta * k
    orbit.phi += (orbit.goalPhi - orbit.phi) * k
    const sp = Math.sin(orbit.phi), r = orbit.radius
    camera.position.set(
      orbit.target.x + r * sp * Math.cos(orbit.theta),
      orbit.target.y + r * Math.cos(orbit.phi),
      orbit.target.z + r * sp * Math.sin(orbit.theta)
    )
    camera.lookAt(orbit.target)
  }

  const el = renderer.domElement
  el.style.display = 'block'
  el.style.touchAction = 'none'

  el.addEventListener('pointerdown', (e) => {
    dragging = true; moved = 0
    downX = e.clientX; downY = e.clientY
    autoRotate = false
    el.setPointerCapture(e.pointerId)
  })
  el.addEventListener('pointermove', (e) => {
    if (e.isPrimary === false) return
    if (!dragging) return
    const dx = e.clientX - downX, dy = e.clientY - downY
    moved += Math.abs(dx) + Math.abs(dy)
    downX = e.clientX; downY = e.clientY
    if (mode === 'drive') return // 开车模式下拖拽不转镜头
    orbit.goalTheta -= dx * 0.0052
    orbit.theta -= dx * 0.0052
    orbit.goalPhi = Math.min(1.35, Math.max(0.45, orbit.goalPhi - dy * 0.003))
    orbit.phi = Math.min(1.35, Math.max(0.45, orbit.phi - dy * 0.003))
  })
  el.addEventListener('pointerup', (e) => {
    dragging = false
    if (moved < 8) handleClick(e)
  })
  el.addEventListener('wheel', (e) => {
    e.preventDefault()
    autoRotate = false
    if (mode === 'drive') { // 开车模式：滚轮调跟车距离
      chaseDist = Math.min(15, Math.max(7, chaseDist * (1 + e.deltaY * 0.001)))
      return
    }
    const f = 1 + e.deltaY * 0.001
    orbit.goalRadius = Math.min(48, Math.max(13, orbit.goalRadius * f))
    orbit.radius = Math.min(48, Math.max(13, orbit.radius * f))
  }, { passive: false })
  // 双指缩放
  el.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2) {
      const d = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      )
      if (pinchD > 0) {
        const f = pinchD / d
        orbit.goalRadius = Math.min(48, Math.max(13, orbit.goalRadius * f))
      }
      pinchD = d
    }
  }, { passive: true })
  el.addEventListener('touchend', () => { pinchD = 0 })

  const ray = new THREE.Raycaster()
  const ptr = new THREE.Vector2()
  function handleClick(e) {
    const rect = el.getBoundingClientRect()
    ptr.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    ptr.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
    ray.setFromCamera(ptr, camera)
    const hits = ray.intersectObjects(pickables, true)
    if (!hits.length) return
    let o = hits[0].object
    while (o && !o.userData.moduleId) o = o.parent
    if (!o) return
    const mod = modules.find((m) => m.id === o.userData.moduleId)
    if (!mod) return
    if (mode === 'drive') {
      // 开车模式：点击建筑手动选中（开车离开后解锁）
      const p = car.pos
      manualLock = { id: mod.id, x: p.x, z: p.z }
      zoneId = mod.id
    } else {
      focusTo(mod.id)
    }
    if (hooks.onSelect) hooks.onSelect(mod)
  }

  function focusTo(moduleId) {
    const wrap = pickables.find((p) => p.userData.moduleId === moduleId)
    if (!wrap) return
    autoRotate = false
    orbit.goalTarget.set(wrap.position.x, 2.6, wrap.position.z)
    orbit.goalRadius = 11
    orbit.goalPhi = 1.08
  }
  function resetView() {
    autoRotate = false
    orbit.goalTarget.set(0, 2.2, 0)
    orbit.goalRadius = 30
    orbit.goalPhi = 1.02
  }

  /* ---------- 主循环 ---------- */
  const clock = new THREE.Clock()
  const STEP = 1 / 60
  const ZERO_INPUT = { throttle: 0, steer: 0, brake: false, boost: false }
  const _chase = new THREE.Vector3()
  const _v3 = new THREE.Vector3()
  let acc = 0
  let dustAcc = 0
  let raf = 0
  let destroyed = false
  function loop() {
    if (destroyed) return
    const dt = Math.min(0.05, clock.getDelta())
    const t = clock.elapsedTime
    if (mode === 'drive') {
      pollKeys()
      acc += dt
      let n = 0, ev = null
      while (acc >= STEP && n < 4) { ev = car.step(STEP, input); phys.step(); acc -= STEP; n++ }
      const cp = car.pos
      if (ev) {
        if (ev.jumped) { boing(); tracker.unlock('first_jump') }
        if (ev.landed) { thud(); particles.burst(cp.x, 0.3, cp.z, 8) }
        if (ev.crashed) {
          thud(); tracker.unlock('crash')
          particles.burst(cp.x, 0.9, cp.z, 10, { vy: 2.5, size: 1.1 })
        }
      }
      const spd = Math.abs(car.speed)
      if (spd > 3) tracker.unlock('first_drive')
      if (car.speed > 15) tracker.unlock('speed')
      // 尘土
      dustAcc += dt
      if (spd > 6 && dustAcc > 0.06) {
        dustAcc = 0
        const yaw = car.yaw
        const fx = Math.sin(yaw), fz = Math.cos(yaw)
        const drift = Math.abs(input.steer) > 0.55 && spd > 8
        particles.spawn(
          cp.x - fx * 1.7 + (Math.random() - 0.5), 0.35, cp.z - fz * 1.7 + (Math.random() - 0.5),
          { vx: -fx * 2, vy: 1.2 + Math.random(), vz: -fz * 2, life: 0.7, size: drift ? 1.1 : 0.75 }
        )
      }
      checkZone()
      engineUpdate(Math.min(1, spd / 17), input.boost, true)
      // 追踪镜头
      const yaw = car.yaw
      const fx = Math.sin(yaw), fz = Math.cos(yaw)
      _chase.set(cp.x - fx * chaseDist, 5.2, cp.z - fz * chaseDist)
      camera.position.lerp(_chase, 1 - Math.exp(-4.5 * dt))
      camera.lookAt(cp.x + fx * 4, 1.7, cp.z + fz * 4)
      // 阴影跟随车辆
      sun.position.set(cp.x + 22, 30, cp.z + 14)
      sun.target.position.set(cp.x, 0, cp.z)
      sun.target.updateMatrixWorld()
    } else {
      if (autoRotate && !dragging) {
        orbit.goalTheta += dt * 0.06
        orbit.theta += dt * 0.06
      }
      applyOrbit(dt)
      acc += dt
      let n = 0
      while (acc >= STEP && n < 4) { car.step(STEP, ZERO_INPUT); phys.step(); acc -= STEP; n++ }
      engineUpdate(0, false, false)
    }
    // 喇叭气泡计时
    if (honkT > 0) { honkT -= dt; if (honkT <= 0) jeep.bubble.visible = false }
    particles.update(dt)
    // 云漂移
    for (const c of clouds) {
      c.g.position.x += c.v * dt
      if (c.g.position.x > 100) c.g.position.x = -100
    }
    // 标签浮动
    for (const l of labels) l.sp.position.y = l.baseY + Math.sin(t * 1.6 + l.phase) * 0.16
    renderer.render(scene, camera)
    raf = requestAnimationFrame(loop)
  }

  function onResize() {
    const w = container.clientWidth || 800
    const h = container.clientHeight || 600
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  }
  window.addEventListener('resize', onResize)

  loop()

  return {
    focusTo,
    resetView,
    setMode,
    getMode: () => mode,
    respawn: () => car.respawn(),
    input, // 摇杆写入 joyThrottle / joySteer
    destroy() {
      destroyed = true
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose()
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material]
          ms.forEach((m) => { if (m.map) m.map.dispose(); m.dispose() })
        }
      })
      renderer.dispose()
      if (el.parentNode === container) container.removeChild(el)
    },
  }
}
