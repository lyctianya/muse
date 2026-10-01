/* 世界装饰：bruno-simon.com 原站道具模型（MIT，见 /hub/ATTRIBUTION.md）
   decorateWorld 返回碰撞体描述，供物理世界使用 */
import { PALETTE } from './palette.js'
import { roadTexture, signTexture } from './textures.js'
import { loadOak, loadBirch, loadCherry, loadLamp, loadFence, loadBench, loadPlayground } from './brunoAssets.js'

let THREE = null
async function three() {
  if (!THREE) THREE = await import('three')
  return THREE
}

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0.02, ...opts })
}

/* 带中央虚线的柏油路 */
export async function makeRoads(scene, modules, radius) {
  await three()
  const tex = await roadTexture()
  modules.forEach((m, i) => {
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    const len = radius - 4.6
    const t = tex.clone()
    t.needsUpdate = true
    t.repeat.set(1, Math.max(2, Math.round(len / 3)))
    const road = new THREE.Mesh(
      new THREE.PlaneGeometry(3.0, len),
      new THREE.MeshStandardMaterial({ map: t, roughness: 1 })
    )
    road.rotation.x = -Math.PI / 2
    road.rotation.z = -a + Math.PI / 2
    const mid = 4.6 + len / 2
    road.position.set(Math.cos(a) * mid, 0.03, Math.sin(a) * mid)
    road.receiveShadow = true
    scene.add(road)
  })
}

/* 木质指示牌：指向每栋建筑 */
export async function makeSignposts(scene, modules) {
  await three()
  for (let i = 0; i < modules.length; i++) {
    const m = modules[i]
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    const r = 6.2
    const g = new THREE.Group()
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 1.9, 8), mat(PALETTE.trunk))
    post.position.y = 0.95
    post.castShadow = true
    g.add(post)
    const board = new THREE.Mesh(
      new THREE.BoxGeometry(1.7, 0.62, 0.08),
      new THREE.MeshStandardMaterial({ map: await signTexture(m.title), roughness: 0.9 })
    )
    board.position.y = 1.75
    board.castShadow = true
    g.add(board)
    g.position.set(Math.cos(a) * r, 0, Math.sin(a) * r)
    g.rotation.y = -a
    scene.add(g)
  }
}

/* 湖 + 小桥 */
export async function makeLake(scene) {
  await three()
  const lake = new THREE.Group()
  const water = new THREE.Mesh(
    new THREE.CircleGeometry(3.4, 36),
    new THREE.MeshStandardMaterial({ color: PALETTE.pond, roughness: 0.15, metalness: 0.25 })
  )
  water.rotation.x = -Math.PI / 2
  water.position.y = 0.05
  water.receiveShadow = true
  lake.add(water)
  const sand = new THREE.Mesh(new THREE.RingGeometry(3.4, 4.1, 36), mat(0xead9a8, { roughness: 1 }))
  sand.rotation.x = -Math.PI / 2
  sand.position.y = 0.04
  sand.receiveShadow = true
  lake.add(sand)
  for (let i = 0; i < 5; i++) {
    const plank = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.1, 0.62), mat(PALETTE.wood))
    plank.position.set(-1.24 + i * 0.62, 0.35 + Math.sin((i / 4) * Math.PI) * 0.35, 0)
    plank.rotation.z = Math.cos((i / 4) * Math.PI) * 0.18
    plank.castShadow = true
    lake.add(plank)
  }
  for (const sz of [-0.75, 0.75]) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.08, 0.08), mat(PALETTE.trunk))
    rail.position.set(0, 1.05, sz)
    rail.castShadow = true
    lake.add(rail)
    for (const px of [-1.4, 0, 1.4]) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.75, 0.09), mat(PALETTE.trunk))
      post.position.set(px, 0.7, sz)
      lake.add(post)
    }
  }
  lake.position.set(21, 0, 13)
  lake.rotation.y = 0.6
  scene.add(lake)
}

/* 主装饰函数：原站道具摆放到我们的世界 */
export async function decorateWorld(scene, modules, radius, zonePts) {
  await three()
  const cylinders = [] // {x, z, r, h} 树干/灯杆
  const boxes = []      // {x, z, hx, hy, hz} 长椅/游乐场/栅栏
  const placed = []
  const avoid = [...zonePts, { x: 0, z: 0 }, { x: 21, z: 13 }, { x: 25, z: -16 }]

  function clear(x, z, minD = 4) {
    if (Math.hypot(x, z) > 35) return false
    for (const p of avoid) if (Math.hypot(x - p.x, z - p.z) < minD) return false
    for (const p of placed) if (Math.hypot(x - p.x, z - p.z) < 2.5) return false
    return true
  }
  function spot(minR, maxR, minD = 4) {
    for (let t = 0; t < 50; t++) {
      const a = Math.random() * Math.PI * 2
      const r = minR + Math.random() * (maxR - minR)
      const x = Math.cos(a) * r, z = Math.sin(a) * r
      if (clear(x, z, minD)) { placed.push({ x, z }); return { x, z } }
    }
    return null
  }

  // 原站树木：橡树 / 白桦 / 樱桃树
  const treeLoaders = [loadOak, loadBirch, loadCherry]
  for (let i = 0; i < 18; i++) {
    const s = spot(20, 33)
    if (!s) continue
    const tree = await treeLoaders[i % 3]()
    const sc = 0.8 + Math.random() * 0.7
    tree.scale.setScalar(sc)
    tree.rotation.y = Math.random() * Math.PI * 2
    tree.position.set(s.x, 0, s.z)
    scene.add(tree)
    cylinders.push({ x: s.x, z: s.z, r: 0.35 * sc, h: 1.4 })
  }

  // 原站路灯：沿道路两侧
  const lampTpl = await loadLamp()
  modules.forEach((m, i) => {
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    for (const [rr, side] of [[9, 1], [13, -1]]) {
      const la = a + side * 0.10
      const x = Math.cos(la) * rr, z = Math.sin(la) * rr
      const lamp = lampTpl.clone(true)
      lamp.position.set(x, 0, z)
      lamp.rotation.y = Math.random() * Math.PI * 2
      scene.add(lamp)
      cylinders.push({ x, z, r: 0.18, h: 3.2 })
    }
  })

  // 原站长椅：广场周围
  const benchTpl = await loadBench()
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 + 0.4
    const x = Math.cos(a) * 7.6, z = Math.sin(a) * 7.6
    const bench = benchTpl.clone(true)
    bench.position.set(x, 0, z)
    bench.rotation.y = -a + Math.PI / 2
    scene.add(bench)
    boxes.push({ x, z, hx: 1.1, hy: 0.6, hz: 0.5 })
    placed.push({ x, z })
  }

  // 原站游乐场：独立游乐区
  const playground = await loadPlayground()
  playground.position.set(25, 0, -16)
  playground.rotation.y = 0.5
  scene.add(playground)
  boxes.push({ x: 25, z: -16, hx: 7, hy: 2.5, hz: 7 })

  // 原站栅栏：围出游乐区
  const fenceTpl = await loadFence()
  const fr = 10.5
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2
    // 留一个缺口方便开车进去
    if (i === 2) continue
    const x = 25 + Math.cos(a) * fr, z = -16 + Math.sin(a) * fr
    const fence = fenceTpl.clone(true)
    fence.position.set(x, 0.42, z)
    fence.rotation.y = -a + Math.PI / 2
    scene.add(fence)
  }

  return { cylinders, boxes }
}
