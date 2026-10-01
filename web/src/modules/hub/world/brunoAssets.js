/* bruno-simon.com 原站素材加载（MIT，见 /hub/ATTRIBUTION.md）
   模型 baked 了原站世界坐标，这里只提取"模板"并重新摆放到我们的世界 */
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'

// 原站部分道具用了 Draco 网格压缩，解码器放在 /hub/draco/
const draco = new DRACOLoader()
draco.setDecoderPath('/hub/draco/')
const loader = new GLTFLoader()
loader.setDRACOLoader(draco)
const cache = new Map()

export async function loadGLB(path) {
  if (cache.has(path)) return cache.get(path)
  const p = loader.loadAsync(path).then((gltf) => {
    gltf.scene.traverse((o) => {
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true }
    })
    return gltf.scene
  })
  cache.set(path, p)
  return p
}

/* 把对象（含子节点）拼成一个可复用的模板组 */
export function groupOf(...objects) {
  const g = new THREE.Group()
  for (const o of objects) g.add(o.clone(true))
  return g
}

/* 在场景图中按名称找模板节点 */
export function findByName(root, pattern) {
  const out = []
  root.traverse((o) => {
    if (o.name && pattern.test(o.name)) out.push(o)
  })
  return out
}

/* 单棵橡树：整个文件就是一棵摆在原点的树 */
export async function loadOak() {
  const scene = await loadGLB('/hub/props/oak.glb')
  return groupOf(...scene.children)
}

export async function loadBirch() {
  const scene = await loadGLB('/hub/props/birch.glb')
  return groupOf(...scene.children)
}

export async function loadCherry() {
  const scene = await loadGLB('/hub/props/cherry.glb')
  return groupOf(...scene.children)
}

/* 取第一个 placement empty 的子节点作为模板（视觉件是其子节点，局部坐标即模板） */
function templateFromFirstPlacement(scene, pattern) {
  const placements = findByName(scene, pattern)
  const g = new THREE.Group()
  if (!placements.length) return g
  for (const child of [...placements[0].children]) {
    g.add(child.clone(true))
  }
  return g
}

/* 路灯 */
export async function loadLamp() {
  const scene = await loadGLB('/hub/props/lamps.glb')
  return templateFromFirstPlacement(scene, /^poleLight\./)
}

/* 栅栏段 */
export async function loadFence() {
  const scene = await loadGLB('/hub/props/fences.glb')
  return templateFromFirstPlacement(scene, /^fencePhysicalDynamic\./)
}

/* 长椅 */
export async function loadBench() {
  const scene = await loadGLB('/hub/props/benches.glb')
  return templateFromFirstPlacement(scene, /^benchPhysicalDynamic/)
}

/* 游乐场：整体搬运并回正到原点 */
export async function loadPlayground() {
  const scene = await loadGLB('/hub/props/playground.glb')
  const g = groupOf(...scene.children)
  const box = new THREE.Box3().setFromObject(g)
  const c = box.getCenter(new THREE.Vector3())
  g.position.set(-c.x, -box.min.y, -c.z)
  const wrap = new THREE.Group()
  wrap.add(g)
  return wrap
}

/* 吉普车：返回 { root(模型空间), wheelTemplate }，调用方负责摆轮子 */
export async function loadJeep() {
  const scene = await loadGLB('/hub/vehicle/jeep.glb')
  const root = new THREE.Group()
  for (const child of [...scene.children]) root.add(child.clone(true))
  const wheelTemplate = findByName(root, /^wheelContainer\./)[0]
  return { root, wheelTemplate }
}
