/* 3D 菜单世界：场景装配 + 轨道镜头 + 点击导航 */
import { PALETTE, MODULE_STYLE } from './palette.js'
import { BUILDERS } from './buildings.js'
import { makeLabel } from './labels.js'
import { buildJeep, createCar } from './car.js'

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

const RADIUS = 16 // 建筑环绕半径

function cssColor(hex) {
  return '#' + hex.toString(16).padStart(6, '0')
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
  scene.fog = new THREE.Fog(PALETTE.fog, 55, 115)

  const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 300)

  // 灯光
  scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x9aa86b, 0.95))
  const sun = new THREE.DirectionalLight(0xfff1d6, 1.7)
  sun.position.set(22, 30, 14)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  sun.shadow.camera.left = -34; sun.shadow.camera.right = 34
  sun.shadow.camera.top = 34; sun.shadow.camera.bottom = -34
  sun.shadow.camera.far = 90
  sun.shadow.bias = -0.0004
  scene.add(sun)

  // 地面
  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(40, 48),
    new THREE.MeshStandardMaterial({ color: PALETTE.ground, roughness: 1 })
  )
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  // 中心广场 + 纪念碑
  const plaza = new THREE.Mesh(
    new THREE.CircleGeometry(4.6, 40),
    new THREE.MeshStandardMaterial({ color: PALETTE.plaza, roughness: 0.9 })
  )
  plaza.rotation.x = -Math.PI / 2
  plaza.position.y = 0.02
  plaza.receiveShadow = true
  scene.add(plaza)
  const obelisk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.35, 0.95, 5.2, 4),
    new THREE.MeshStandardMaterial({ color: PALETTE.gold, roughness: 0.4, metalness: 0.35 })
  )
  obelisk.position.y = 2.6
  obelisk.castShadow = true
  scene.add(obelisk)
  const museLabel = await makeLabel('Muse', '#d3a24a')
  museLabel.position.set(0, 6.4, 0)
  scene.add(museLabel)

  // 道路（中心到每栋建筑）
  const roadMat = new THREE.MeshStandardMaterial({ color: PALETTE.road, roughness: 1 })
  const modules = hooks.modules || MODULES
  modules.forEach((m, i) => {
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    const len = RADIUS - 4.6
    const road = new THREE.Mesh(new THREE.PlaneGeometry(2.6, len), roadMat)
    road.rotation.x = -Math.PI / 2
    road.rotation.z = -a + Math.PI / 2
    const mid = 4.6 + len / 2
    road.position.set(Math.cos(a) * mid, 0.03, Math.sin(a) * mid)
    road.receiveShadow = true
    scene.add(road)
  })

  // 建筑
  const pickables = []
  const solids = [] // 用于生成物理碰撞体（不含悬浮标签）
  const zonePts = [] // 触发区：建筑位置
  const labels = []
  const spinners = []
  const bobbers = []
  for (let i = 0; i < modules.length; i++) {
    const m = modules[i]
    const builder = BUILDERS[m.id]
    if (!builder) continue
    const g = await builder()
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    // 位移组包裹：保留建筑内部的 position.y（如 gallery 的 0.4）
    const innerY = g.position.y
    const wrap = new THREE.Group()
    wrap.add(g)
    g.position.set(0, innerY, 0)
    wrap.position.set(Math.cos(a) * RADIUS, 0, Math.sin(a) * RADIUS)
    wrap.rotation.y = -a - Math.PI / 2 // 面向中心
    wrap.userData.moduleId = m.id
    solids.push(g)
    zonePts.push({ id: m.id, x: wrap.position.x, z: wrap.position.z })
    const accent = cssColor((MODULE_STYLE[m.id] || {}).accent || 0xd3a24a)
    const label = await makeLabel(m.title, accent)
    label.position.set(0, g.userData.labelY || 5, 0)
    wrap.add(label)
    labels.push({ sp: label, baseY: label.position.y, phase: Math.random() * 6 })
    if (g.userData.spin) spinners.push(g.userData.spin)
    if (g.userData.bob) bobbers.push({ o: g.userData.bob, baseY: g.userData.bob.position.y, phase: Math.random() * 6 })
    g.traverse((o) => { o.userData.moduleId = m.id })
    scene.add(wrap)
    pickables.push(wrap)
  }

  // 树
  const treePos = []
  for (let i = 0; i < 16; i++) {
    const a = Math.random() * Math.PI * 2
    const r = 22 + Math.random() * 12
    const x = Math.cos(a) * r, z = Math.sin(a) * r
    const tree = new THREE.Group()
    const trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.22, 0.3, 1.2, 8),
      new THREE.MeshStandardMaterial({ color: PALETTE.trunk, roughness: 1 })
    )
    trunk.position.y = 0.6
    trunk.castShadow = true
    tree.add(trunk)
    const s = 0.9 + Math.random() * 0.7
    const c1 = new THREE.Mesh(
      new THREE.ConeGeometry(1.3 * s, 2.0 * s, 8),
      new THREE.MeshStandardMaterial({ color: Math.random() > 0.5 ? PALETTE.leaf : PALETTE.leafDark, roughness: 1 })
    )
    c1.position.y = 2.0 * s
    c1.castShadow = true
    tree.add(c1)
    const c2 = new THREE.Mesh(
      new THREE.ConeGeometry(0.95 * s, 1.5 * s, 8),
      new THREE.MeshStandardMaterial({ color: PALETTE.leaf, roughness: 1 })
    )
    c2.position.y = 3.0 * s
    c2.castShadow = true
    tree.add(c2)
    tree.position.set(x, 0, z)
    tree.rotation.y = Math.random() * 6
    scene.add(tree)
    treePos.push(tree)
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
    cl.position.set(-38 + Math.random() * 76, 15 + Math.random() * 5, -25 + Math.random() * 40)
    scene.add(cl)
    clouds.push({ g: cl, v: 0.4 + Math.random() * 0.5 })
  }

  // 池塘
  const pond = new THREE.Mesh(
    new THREE.CircleGeometry(3.2, 32),
    new THREE.MeshStandardMaterial({ color: PALETTE.pond, roughness: 0.25, metalness: 0.1 })
  )
  pond.rotation.x = -Math.PI / 2
  pond.position.set(20, 0.04, 14)
  pond.receiveShadow = true
  scene.add(pond)

  /* ---------- Rapier 物理 ---------- */
  const rapierMod = await import('@dimforge/rapier3d-compat')
  const RAPIER = rapierMod.default
  await RAPIER.init()
  const phys = new RAPIER.World({ x: 0, y: -9.81, z: 0 })
  phys.timestep = 1 / 60
  phys.createCollider(RAPIER.ColliderDesc.cuboid(40, 0.5, 40).setTranslation(0, -0.5, 0))

  scene.updateMatrixWorld(true)
  const _bbox = new THREE.Box3()
  const _size = new THREE.Vector3()
  const _center = new THREE.Vector3()
  function addSolidCollider(obj) {
    _bbox.setFromObject(obj)
    _bbox.getSize(_size)
    _bbox.getCenter(_center)
    if (_size.x <= 0 || _size.y <= 0 || _size.z <= 0) return
    phys.createCollider(
      RAPIER.ColliderDesc.cuboid(_size.x / 2, _size.y / 2, _size.z / 2)
        .setTranslation(_center.x, _center.y, _center.z)
        .setFriction(0.4)
    )
  }
  for (const s of solids) addSolidCollider(s)
  addSolidCollider(obelisk)
  for (const t of treePos) {
    phys.createCollider(RAPIER.ColliderDesc.cylinder(0.6, 0.28).setTranslation(t.position.x, 0.6, t.position.z))
  }

  /* ---------- 吉普车 ---------- */
  const jeep = await buildJeep()
  scene.add(jeep.carrier)
  const car = createCar(RAPIER, phys, jeep)
  let chaseDist = 10.5
  { // 开车模式初始机位
    const p = car.pos, yaw = car.yaw
    const fx = Math.sin(yaw), fz = Math.cos(yaw)
    camera.position.set(p.x - fx * chaseDist, 5.2, p.z - fz * chaseDist)
    camera.lookAt(p.x + fx * 4, 1.7, p.z + fz * 4)
  }

  /* ---------- 输入（键盘 + 摇杆） ---------- */
  const input = { throttle: 0, steer: 0, brake: false, boost: false, joyThrottle: 0, joySteer: 0 }
  const keys = new Set()
  const clamp01 = (v) => Math.max(-1, Math.min(1, v))
  function onKeyDown(e) {
    const k = e.key.toLowerCase()
    if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' '].includes(k)) e.preventDefault()
    if (k === 'r' && mode === 'drive') car.respawn()
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
    input.brake = keys.has(' ')
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
    let best = null, bd = 36 // 6^2
    for (const z of zonePts) {
      const dx = p.x - z.x, dz = p.z - z.z
      const d2 = dx * dx + dz * dz
      if (d2 < bd) { bd = d2; best = z.id }
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
  let acc = 0
  let raf = 0
  let destroyed = false
  function loop() {
    if (destroyed) return
    const dt = Math.min(0.05, clock.getDelta())
    const t = clock.elapsedTime
    if (mode === 'drive') {
      pollKeys()
      acc += dt
      let n = 0
      while (acc >= STEP && n < 4) { car.step(STEP, input); phys.step(); acc -= STEP; n++ }
      checkZone()
      // 追踪镜头
      const p = car.pos, yaw = car.yaw
      const fx = Math.sin(yaw), fz = Math.cos(yaw)
      _chase.set(p.x - fx * chaseDist, 5.2, p.z - fz * chaseDist)
      camera.position.lerp(_chase, 1 - Math.exp(-4.5 * dt))
      camera.lookAt(p.x + fx * 4, 1.7, p.z + fz * 4)
    } else {
      if (autoRotate && !dragging) {
        orbit.goalTheta += dt * 0.06
        orbit.theta += dt * 0.06
      }
      applyOrbit(dt)
      acc += dt
      let n = 0
      while (acc >= STEP && n < 4) { car.step(STEP, ZERO_INPUT); phys.step(); acc -= STEP; n++ }
    }
    // 云漂移
    for (const c of clouds) {
      c.g.position.x += c.v * dt
      if (c.g.position.x > 42) c.g.position.x = -42
    }
    // 齿轮旋转
    for (const s of spinners) s.rotation.z -= dt * 0.8
    // 钥匙浮动
    for (const b of bobbers) b.o.position.y = b.baseY + Math.sin(t * 2 + b.phase) * 0.22
    // 标签浮动
    for (const l of labels) l.sp.position.y = l.baseY + Math.sin(t * 1.6 + l.phase) * 0.16
    museLabel.position.y = 6.4 + Math.sin(t * 1.4) * 0.15
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
