/* 世界装饰：纹理路、路灯、植被、指示牌、湖与桥 */
import { PALETTE } from './palette.js'
import { roadTexture, signTexture } from './textures.js'

let THREE = null
async function three() {
  if (!THREE) THREE = await import('three')
  return THREE
}

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0.02, ...opts })
}
function shadowed(m) { m.castShadow = true; m.receiveShadow = true; return m }

/* 带中央虚线的柏油路 */
export async function makeRoads(scene, modules, radius) {
  await three()
  const tex = await roadTexture()
  const roadMat = new THREE.MeshStandardMaterial({ map: tex, roughness: 1 })
  const roads = []
  modules.forEach((m, i) => {
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    const len = radius - 4.6
    const road = new THREE.Mesh(new THREE.PlaneGeometry(3.0, len), roadMat.clone())
    road.material.map = tex.clone()
    road.material.map.needsUpdate = true
    road.material.map.repeat.set(1, Math.max(2, Math.round(len / 3)))
    road.rotation.x = -Math.PI / 2
    road.rotation.z = -a + Math.PI / 2
    const mid = 4.6 + len / 2
    road.position.set(Math.cos(a) * mid, 0.03, Math.sin(a) * mid)
    road.receiveShadow = true
    scene.add(road)
    roads.push({ angle: a, mid })
  })
  return roads
}

/* 路灯：杆 + 暖光灯头（无真实光源，靠 emissive） */
export async function makeLamps(scene, modules, radius) {
  await three()
  const lamps = []
  modules.forEach((m, i) => {
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    for (const side of [-1, 1]) {
      const r = 8.5
      const la = a + side * 0.09
      const x = Math.cos(la) * r, z = Math.sin(la) * r
      const g = new THREE.Group()
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.12, 3.4, 8), mat(PALETTE.dark))
      pole.position.y = 1.7
      pole.castShadow = true
      g.add(pole)
      const arm = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.08, 0.08), mat(PALETTE.dark))
      arm.position.set(0.35, 3.35, 0)
      g.add(arm)
      const bulb = new THREE.Mesh(
        new THREE.SphereGeometry(0.22, 10, 10),
        new THREE.MeshStandardMaterial({ color: 0xfff4c2, emissive: 0xffd970, emissiveIntensity: 1.2 })
      )
      bulb.position.set(0.75, 3.2, 0)
      g.add(bulb)
      const cap = new THREE.Mesh(new THREE.ConeGeometry(0.34, 0.25, 8), mat(PALETTE.dark))
      cap.position.set(0.75, 3.45, 0)
      g.add(cap)
      g.position.set(x, 0, z)
      g.rotation.y = -la + Math.PI / 2
      scene.add(g)
      lamps.push(g)
    }
  })
  return lamps
}

/* 灌木 / 岩石 / 花 */
export async function makeNature(scene, avoid = []) {
  await three()
  const placed = []
  function clear(x, z, minD = 3.5) {
    if (Math.hypot(x, z) > 36) return false
    for (const p of avoid) if (Math.hypot(x - p.x, z - p.z) < minD) return false
    for (const p of placed) if (Math.hypot(x - p.x, z - p.z) < 2.2) return false
    return true
  }
  function spot(minR, maxR) {
    for (let t = 0; t < 40; t++) {
      const a = Math.random() * Math.PI * 2
      const r = minR + Math.random() * (maxR - minR)
      const x = Math.cos(a) * r, z = Math.sin(a) * r
      if (clear(x, z)) { placed.push({ x, z }); return { x, z } }
    }
    return null
  }
  // 灌木
  for (let i = 0; i < 14; i++) {
    const s = spot(6, 34)
    if (!s) continue
    const b = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.55 + Math.random() * 0.5, 0),
      mat(Math.random() > 0.5 ? PALETTE.leaf : PALETTE.leafDark, { roughness: 1 })
    )
    b.position.set(s.x, 0.45, s.z)
    b.scale.y = 0.75
    shadowed(b)
    scene.add(b)
  }
  // 岩石
  for (let i = 0; i < 8; i++) {
    const s = spot(10, 34)
    if (!s) continue
    const r = new THREE.Mesh(
      new THREE.DodecahedronGeometry(0.4 + Math.random() * 0.45, 0),
      mat(0x9aa0a8, { roughness: 1 })
    )
    r.position.set(s.x, 0.3, s.z)
    r.rotation.set(Math.random() * 3, Math.random() * 3, 0)
    shadowed(r)
    scene.add(r)
  }
  // 花
  const petalCols = [0xe5484d, 0xff8fa3, 0xf4d35e, 0xffffff, 0x9b5de5]
  for (let i = 0; i < 26; i++) {
    const s = spot(5.5, 33)
    if (!s) continue
    const g = new THREE.Group()
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.5, 6), mat(PALETTE.leafDark))
    stem.position.y = 0.25
    g.add(stem)
    const head = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.14, 0),
      mat(petalCols[i % petalCols.length], { roughness: 0.6 })
    )
    head.position.y = 0.55
    g.add(head)
    g.position.set(s.x, 0, s.z)
    scene.add(g)
  }
}

/* 木质指示牌：指向每栋建筑 */
export async function makeSignposts(scene, modules, radius) {
  await three()
  for (let i = 0; i < modules.length; i++) {
    const m = modules[i]
    const a = (i / modules.length) * Math.PI * 2 + Math.PI / modules.length
    const r = 6.2
    const x = Math.cos(a) * r, z = Math.sin(a) * r
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
    g.position.set(x, 0, z)
    // 牌面朝向道路（切向），箭头指向建筑
    g.rotation.y = -a - Math.PI / 2 + Math.PI / 2
    scene.add(g)
  }
}

/* 湖 + 小桥（微光水面） */
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
  // 沙滩边
  const sand = new THREE.Mesh(
    new THREE.RingGeometry(3.4, 4.1, 36),
    mat(0xead9a8, { roughness: 1 })
  )
  sand.rotation.x = -Math.PI / 2
  sand.position.y = 0.04
  sand.receiveShadow = true
  lake.add(sand)
  // 小桥：5 块木板 + 栏杆
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
  // 荷叶
  for (let i = 0; i < 4; i++) {
    const leaf = new THREE.Mesh(new THREE.CircleGeometry(0.32, 10, 0, 5.2), mat(PALETTE.leafDark))
    leaf.rotation.x = -Math.PI / 2
    leaf.position.set(Math.cos(i * 1.7) * 1.8, 0.07, Math.sin(i * 2.3) * 1.8 + 1.2)
    lake.add(leaf)
  }
  lake.position.set(21, 0, 13)
  lake.rotation.y = 0.6
  scene.add(lake)
  return { group: lake, water }
}

/* 广场周围花坛 */
export async function makeFlowerBeds(scene) {
  await three()
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.26
    const x = Math.cos(a) * 6.4, z = Math.sin(a) * 6.4
    const bed = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.1, 0.35, 12), mat(PALETTE.trunk))
    bed.position.set(x, 0.17, z)
    bed.castShadow = bed.receiveShadow = true
    scene.add(bed)
    const soil = new THREE.Mesh(new THREE.CircleGeometry(0.92, 12), mat(0x5e3d26, { roughness: 1 }))
    soil.rotation.x = -Math.PI / 2
    soil.position.set(x, 0.36, z)
    scene.add(soil)
    for (let j = 0; j < 5; j++) {
      const fa = (j / 5) * Math.PI * 2
      const fx = x + Math.cos(fa) * 0.55, fz = z + Math.sin(fa) * 0.55
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.4, 6), mat(PALETTE.leafDark))
      stem.position.set(fx, 0.55, fz)
      scene.add(stem)
      const head = new THREE.Mesh(
        new THREE.IcosahedronGeometry(0.13, 0),
        mat([0xe5484d, 0xf4d35e, 0xff8fa3][j % 3], { roughness: 0.6 })
      )
      head.position.set(fx, 0.8, fz)
      scene.add(head)
    }
  }
}
