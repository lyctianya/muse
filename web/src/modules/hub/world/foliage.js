/* 程序化树叶：照原站 Foliage.js
   - 80 片 0.8×0.8 平面球形排布，合并为一个几何
   - foliageSDF.png 做 alpha，threshold 0.3
   - 颜色按法线·光照方向在 colorA/B 间渐变
   - InstancedMesh 一次绘制所有树叶 */
import * as THREE from 'three'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'

// 简单可复现随机（原站用 seedrandom('foliage')）
function mulberry32(seed) {
  let a = seed >>> 0
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildFoliageGeometry() {
  const rng = mulberry32(1337)
  const planes = []
  const count = 80
  for (let i = 0; i < count; i++) {
    const plane = new THREE.PlaneGeometry(0.8, 0.8)
    // 球形分布：radius = 1 - rng^3（偏表面），phi/theta 随机
    const radius = 1 - Math.pow(rng(), 3)
    const phi = Math.PI * 2 * rng()
    const theta = Math.PI * rng()
    const x = radius * Math.sin(theta) * Math.cos(phi)
    const y = radius * Math.cos(theta)
    const z = radius * Math.sin(theta) * Math.sin(phi)
    plane.rotateZ(rng() * 9999)
    plane.translate(x, y, z)
    // 法线：平面法线与径向混合 0.85
    const normal = new THREE.Vector3(x, y, z).normalize()
    const pos = plane.attributes.position
    const normArr = new Float32Array(pos.count * 3)
    const v = new THREE.Vector3()
    for (let j = 0; j < pos.count; j++) {
      v.set(pos.getX(j), pos.getY(j), pos.getZ(j))
      // 注意：translate 后的 position 含偏移，需减去中心得平面局部法线方向
      // 简化：直接用径向法线（原站是 lerp，这里取径向）
      normArr[j * 3] = normal.x
      normArr[j * 3 + 1] = normal.y
      normArr[j * 3 + 2] = normal.z
    }
    plane.setAttribute('normal', new THREE.BufferAttribute(normArr, 3))
    planes.push(plane)
  }
  return mergeGeometries(planes)
}

let foliageGeometry = null
let foliageAlphaTex = null

export async function createFoliage(scene, matrices, colorA, colorB) {
  if (!foliageGeometry) foliageGeometry = buildFoliageGeometry()
  if (!foliageAlphaTex) {
    foliageAlphaTex = await new THREE.TextureLoader().loadAsync('/hub/world/foliageSDF.png')
  }
  const cA = new THREE.Color(colorA)
  const cB = new THREE.Color(colorB)
  const mat = new THREE.MeshStandardMaterial({
    alphaMap: foliageAlphaTex,
    alphaTest: 0.3,
    side: THREE.DoubleSide,
    roughness: 0.9,
    metalness: 0,
  })
  // 颜色按法线·光照方向在 colorA/B 间渐变（原站 Foliage colorNode）
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.colorA = { value: cA }
    shader.uniforms.colorB = { value: cB }
    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <map_fragment>',
      `#include <map_fragment>
       {
         // 用几何法线（vNormal 在 view 空间，转回近似世界）
         vec3 nW = normalize(vNormal);
         // 简化：用光照方向 (0.5, 1, 0.3) 做 lambert
         float m = smoothstep(0.0, 1.0, dot(nW, normalize(vec3(0.5, 1.0, 0.3))));
         diffuseColor.rgb = mix(colorA, colorB, m);
       }`
    ).replace(
      'void main() {',
      'uniform vec3 colorA;\nuniform vec3 colorB;\nvoid main() {'
    )
  }
  const inst = new THREE.InstancedMesh(foliageGeometry, mat, matrices.length)
  const m4 = new THREE.Matrix4()
  matrices.forEach((mtx, i) => {
    m4.copy(mtx)
    inst.setMatrixAt(i, m4)
  })
  inst.instanceMatrix.needsUpdate = true
  inst.castShadow = true
  inst.receiveShadow = true
  inst.frustumCulled = false
  scene.add(inst)
  return inst
}
