/* 草地：原站 Grass 的 WebGL 实现
   - InstancedMesh 草叶，顶点着色器做风吹摇摆
   - 在地形草地区域随机分布 */
import * as THREE from 'three'

export function createGrass(scene, count = 3000, area = 180) {
  // 草叶几何：细长三角
  const geo = new THREE.PlaneGeometry(0.08, 0.5, 1, 3)
  geo.translate(0, 0.25, 0) // 底部在原点
  
  const mat = new THREE.MeshStandardMaterial({
    color: 0x7aa832, roughness: 0.9, side: THREE.DoubleSide,
  })
  
  // 风吹摇摆：onBeforeCompile 注入顶点动画
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = { value: 0 }
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nuniform float uTime;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        // 顶部摆动幅度大
        float sway = sin(uTime * 2.0 + float(gl_InstanceID) * 0.5) * 0.08 * position.y * 2.0;
        transformed.x += sway;
        transformed.z += sway * 0.6;
      `)
    mat.userData.shader = shader
  }

  const inst = new THREE.InstancedMesh(geo, mat, count)
  inst.frustumCulled = false
  inst.receiveShadow = true

  const m4 = new THREE.Matrix4()
  const q = new THREE.Quaternion()
  const e = new THREE.Euler()
  const v = new THREE.Vector3()
  const sc = new THREE.Vector3()

  for (let i = 0; i < count; i++) {
    // 随机位置，避开建筑中心区域
    const x = (Math.random() - 0.5) * area
    const z = (Math.random() - 0.5) * area
    // 简单：避开原点附近建筑群
    if (Math.abs(x) < 15 && Math.abs(z) < 15) {
      i--
      continue
    }
    e.set(0, Math.random() * Math.PI * 2, 0)
    q.setFromEuler(e)
    v.set(x, 0.02, z)
    const s = 0.7 + Math.random() * 0.8
    sc.set(s, s * (0.8 + Math.random() * 0.6), s)
    m4.compose(v, q, sc)
    inst.setMatrixAt(i, m4)
  }
  inst.instanceMatrix.needsUpdate = true
  scene.add(inst)

  return {
    mesh: inst,
    update(t) {
      if (mat.userData.shader) {
        mat.userData.shader.uniforms.uTime.value = t
      }
    },
  }
}
