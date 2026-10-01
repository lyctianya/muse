/* bruno-simon.com 完整世界（MIT，见 /hub/ATTRIBUTION.md）
   地形 / 全部建筑 / 布景 / 树木 / 灌木 / 花 —— 坐标均为原站烘焙 */
import * as THREE from 'three'
import { loadGLB } from './brunoAssets.js'

/* 8 模块 → 原站建筑位置（x, z，来自 areas.glb 烘焙坐标） */
export const BUILDING_POS = {
  stock:   { x: 35.76,  z: 13.41,  area: 'projects' },       // 股票
  blog:    { x: 25.84,  z: -0.90,  area: 'career' },         // 博客
  gallery: { x: 28.90,  z: -21.82, area: 'social' },          // 相册
  game:    { x: 2.31,   z: 68.91,  area: 'bowling' },         // 游戏
  tools:   { x: 13.14,  z: 17.68,  area: 'lab' },             // 工具箱
  files:   { x: 52.46,  z: -11.96, area: 'behindTheScene' },  // 文件
  sync:    { x: 70.55,  z: 9.94,   area: 'achievements' },    // 数据更新
  users:   { x: 49.25,  z: 38.52,  area: 'landing' },         // 用户管理
}

export const WORLD_SPAWN = { x: 20, z: 30, yaw: Math.PI * 0.75 }

/* 地形高度场（129x129 float32 raw，x/z ∈ [-96, 96]） */
let heightGrid = null
export async function loadHeightGrid() {
  if (heightGrid) return heightGrid
  const res = await fetch('/hub/world/terrain_heights.raw')
  const buf = await res.arrayBuffer()
  heightGrid = new Float32Array(buf)
  return heightGrid
}
export function groundHeightAt(x, z) {
  if (!heightGrid) return 0
  const N = 129
  const fx = (x + 96) / 192 * (N - 1)
  const fz = (z + 96) / 192 * (N - 1)
  const x0 = Math.max(0, Math.min(N - 2, Math.floor(fx)))
  const z0 = Math.max(0, Math.min(N - 2, Math.floor(fz)))
  const tx = fx - x0, tz = fz - z0
  const h00 = heightGrid[z0 * N + x0], h10 = heightGrid[z0 * N + x0 + 1]
  const h01 = heightGrid[(z0 + 1) * N + x0], h11 = heightGrid[(z0 + 1) * N + x0 + 1]
  return h00 * (1 - tx) * (1 - tz) + h10 * tx * (1 - tz) + h01 * (1 - tx) * tz + h11 * tx * tz
}

/* 按 refs 摆 visual 模板；matFor(name) 可覆盖材质（调色板 UV 在 Draco 下不稳定时用纯色） */
async function instanceFromRefs(scene, visualPath, refsPath, namePrefix, matFor = null) {
  const visual = await loadGLB(visualPath)
  const refs = await loadGLB(refsPath)
  let count = 0
  refs.traverse((o) => {
    if (!o.isMesh && o.name && o.name.startsWith(namePrefix)) {
      const inst = visual.clone(true)
      if (matFor) {
        inst.traverse((m) => {
          if (m.isMesh) {
            const mat = matFor(m.name)
            if (mat) m.material = mat
          }
        })
      }
      inst.position.copy(o.position)
      inst.quaternion.copy(o.quaternion)
      inst.scale.copy(o.scale)
      scene.add(inst)
      count++
    }
  })
  // refs 自身不加入场景（只用它做 placement）
  return count
}

/* 树的纯色材质（按名称区分树干/树叶） */
function treeMaterials(trunkColor, leafColor) {
  const trunk = new THREE.MeshStandardMaterial({ color: trunkColor, roughness: 0.9 })
  const leaf = new THREE.MeshStandardMaterial({ color: leafColor, roughness: 0.9 })
  return (name) => {
    if (!name) return null
    const n = name.toLowerCase()
    if (n.includes('body') || n.includes('trunk')) return trunk
    if (n.includes('leav')) return leaf
    return null
  }
}

export async function loadBrunoWorld(scene) {
  // 地形：贴原站地形纹理（贴图自带手绘色彩，用无光照材质避免被灯光推成霓虹色）
  const terrain = await loadGLB('/hub/world/terrain.glb')
  {
    const tex = await new THREE.TextureLoader().loadAsync('/hub/world/terrain.png')
    tex.colorSpace = THREE.SRGBColorSpace
    terrain.traverse((o) => {
      if (o.isMesh) {
        o.material = new THREE.MeshBasicMaterial({ map: tex })
        o.receiveShadow = true
      }
    })
  }
  scene.add(terrain)
  const areas = await loadGLB('/hub/world/areas.glb')
  scene.add(areas)
  const scenery = await loadGLB('/hub/world/scenery.glb')
  scene.add(scenery)

  // 树木（纯色材质，绕开 Draco 下不稳定的调色板 UV）
  const nb = await instanceFromRefs(scene, '/hub/world/birchVisual.glb', '/hub/world/birchRefs.glb', 'treeBody',
    treeMaterials(0xe8e0d0, 0x86c860))
  const no = await instanceFromRefs(scene, '/hub/world/oakVisual.glb', '/hub/world/oakRefs.glb', 'treeBody',
    treeMaterials(0x8b5a2b, 0x4a9c4a))
  const nc = await instanceFromRefs(scene, '/hub/world/cherryVisual.glb', '/hub/world/cherryRefs.glb', 'treeBody',
    treeMaterials(0x8b5a2b, 0xff9990))

  // 灌木 / 花：自带几何与坐标；灌木无材质，给绿色
  const bushes = await loadGLB('/hub/world/bushesRefs.glb')
  const bushMat = new THREE.MeshStandardMaterial({ color: 0x3f9142, roughness: 0.9 })
  bushes.traverse((o) => { if (o.isMesh) o.material = bushMat })
  scene.add(bushes)
  scene.add(await loadGLB('/hub/world/flowersRefs.glb'))

  console.log(`[hub] 世界加载完成：建筑群 + 地形 + ${nb + no + nc} 棵树 + 灌木花丛`)
  await loadHeightGrid()
  return true
}
