/* bruno-simon.com 完整世界（MIT，见 /hub/ATTRIBUTION.md）
   地形 / 全部建筑 / 布景 / 树木 / 灌木 / 花 —— 坐标均为原站烘焙 */
import * as THREE from 'three'
import { loadGLB } from './brunoAssets.js'
import { createFoliage } from './foliage.js'

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

/* 树木：照原站 Trees.js
   - 树干：InstancedMesh（body 几何 + refs 矩阵，一次绘制）
   - 树叶：程序化 Foliage（80 平面球形排布 + alpha 纹理 + colorA/B 渐变）
   - 返回 { count, positions }（positions 用于碰撞体） */
async function plantTrees(scene, visualPath, refsPath, trunkColor, leafA, leafB) {
  const visual = await loadGLB(visualPath)
  const refs = await loadGLB(refsPath)
  // 找 treeBody 和 treeLeaves
  let bodyMesh = null
  const leavesMeshes = []
  visual.traverse((o) => {
    if (!o.isMesh) return
    const n = (o.name || '').toLowerCase()
    if (n.startsWith('treeleaves')) leavesMeshes.push(o)
    else if (n.startsWith('treebody')) bodyMesh = o
  })
  const positions = []
  const bodyMatrices = []
  const leafMatrices = []
  const m4 = new THREE.Matrix4()
  refs.traverse((o) => {
    // refs GLB 用 "GN Instance" 做树位置（Blender 几何节点导出），treeBody.001 等是模板
    if (o.isMesh || !o.name || o.name !== 'GN Instance') return
    // refs 世界矩阵
    o.updateWorldMatrix(true, false)
    const refMtx = o.matrixWorld.clone()
    positions.push(new THREE.Vector3().setFromMatrixPosition(refMtx))
    if (bodyMesh) {
      bodyMatrices.push(refMtx)
    }
    // 每片树叶：leaves.matrix × ref.matrixWorld（原站 Trees.setLeaves）
    for (const lm of leavesMeshes) {
      lm.updateWorldMatrix(true, false)
      // leaves 在 visual 内的本地矩阵 × ref 世界矩阵
      // 注意 visual 未加入场景，需手动算：visual.matrixWorld 是单位阵
      const leafLocal = lm.matrix.clone()
      const final = new THREE.Matrix4().multiplyMatrices(refMtx, leafLocal)
      leafMatrices.push(final)
    }
  })
  // 树干实例化
  if (bodyMesh && bodyMatrices.length) {
    const trunkMat = new THREE.MeshStandardMaterial({ color: trunkColor, roughness: 0.9 })
    const inst = new THREE.InstancedMesh(bodyMesh.geometry, trunkMat, bodyMatrices.length)
    bodyMatrices.forEach((mtx, i) => inst.setMatrixAt(i, mtx))
    inst.instanceMatrix.needsUpdate = true
    inst.castShadow = true
    inst.receiveShadow = true
    scene.add(inst)
  }
  // 树叶程序化
  if (leafMatrices.length) {
    await createFoliage(scene, leafMatrices, leafA, leafB)
  }
  return { count: positions.length, positions }
}

export async function loadBrunoWorld(scene) {
  // 地形：原站 Terrain.js 把 terrain.png 当数据纹理解码（非颜色贴图！）
  //   B 通道 = 高度 → 查 1×16 渐变（#ffa94e 橙 → #5bc2b9 青 → #13375f 深蓝）
  //   G 通道 = 草地 mask → 与草绿 #b8b62e 混合
  //   R 通道 = 石板 mask → 混石板色
  //   采样 uv = 世界坐标 / 192 + 0.5
  const terrain = await loadGLB('/hub/world/terrain.glb')
  {
    const dataTex = await new THREE.TextureLoader().loadAsync('/hub/world/terrain.png')
    dataTex.colorSpace = THREE.NoColorSpace
    // 高度渐变：1×16，B=0 深蓝（低）→ B=1 橙（高）
    const gc = document.createElement('canvas')
    gc.width = 1; gc.height = 16
    const gctx = gc.getContext('2d')
    const grad = gctx.createLinearGradient(0, 16, 0, 0)
    grad.addColorStop(0, '#13375f')
    grad.addColorStop(0.5, '#5bc2b9')
    grad.addColorStop(1, '#ffa94e')
    gctx.fillStyle = grad
    gctx.fillRect(0, 0, 1, 16)
    const gradTex = new THREE.CanvasTexture(gc)
    gradTex.colorSpace = THREE.SRGBColorSpace
    const terrainMat = new THREE.ShaderMaterial({
      uniforms: {
        dataMap: { value: dataTex },
        gradMap: { value: gradTex },
        grassColor: { value: new THREE.Color('#b8b62e') },
        slabColor: { value: new THREE.Color('#c9a06a') },
      },
      vertexShader: `
        varying vec3 vWorldPos;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorldPos = wp.xyz;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: `
        uniform sampler2D dataMap;
        uniform sampler2D gradMap;
        uniform vec3 grassColor;
        uniform vec3 slabColor;
        varying vec3 vWorldPos;
        void main() {
          vec2 uv = vWorldPos.xz / 192.0 + 0.5;
          vec3 data = texture2D(dataMap, uv).rgb;
          // B = 高度 → 渐变
          vec3 col = texture2D(gradMap, vec2(0.5, data.b)).rgb;
          // G = 草地 mask → 混草绿
          col = mix(col, grassColor, clamp(data.g * 1.2, 0.0, 1.0));
          // R = 石板 mask → 混石板色
          col = mix(col, slabColor, clamp(data.r * 0.85, 0.0, 1.0));
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    })
    terrain.traverse((o) => {
      if (o.isMesh) {
        o.material = terrainMat
        o.receiveShadow = true
      }
    })
  }
  scene.add(terrain)
  const areas = await loadGLB('/hub/world/areas.glb')
  scene.add(areas)
  const scenery = await loadGLB('/hub/world/scenery.glb')
  scene.add(scenery)

  // 树木：原站 Trees 传入 colorA/colorB（非调色板）
  // 白桦 #ff4f2b/#ff903f（橙），橡树 #b4b536/#d8cf3b（橄榄绿），樱桃 #ff6d6d/#ff9990（粉）
  const nb = await plantTrees(scene, '/hub/world/birchVisual.glb', '/hub/world/birchRefs.glb',
    0xe8e0d0, '#ff4f2b', '#ff903f')
  const no = await plantTrees(scene, '/hub/world/oakVisual.glb', '/hub/world/oakRefs.glb',
    0x8b5a2b, '#b4b536', '#d8cf3b')
  const nc = await plantTrees(scene, '/hub/world/cherryVisual.glb', '/hub/world/cherryRefs.glb',
    0x8b5a2b, '#ff6d6d', '#ff9990')

  // 灌木：原站 Bushes = Foliage（#b4b536/#d8cf3b 橄榄绿）
  {
    const bushRefs = await loadGLB('/hub/world/bushesRefs.glb')
    const bushMatrices = []
    bushRefs.traverse((o) => {
      if (o.isMesh) return
      o.updateWorldMatrix(true, false)
      bushMatrices.push(o.matrixWorld.clone())
    })
    if (bushMatrices.length) {
      await createFoliage(scene, bushMatrices, '#b4b536', '#d8cf3b')
    }
  }
  scene.add(await loadGLB('/hub/world/flowersRefs.glb'))

  const treePositions = [...nb.positions, ...no.positions, ...nc.positions]
  console.log(`[hub] 世界加载完成：建筑群 + 地形 + ${treePositions.length} 棵树 + 灌木花丛`)
  await loadHeightGrid()
  return { treePositions }
}
