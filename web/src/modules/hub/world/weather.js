/* 天气：原站 Weather 的 WebGL 实现
   - 雨粒子系统，可开关
   - 雨滴为拉伸的线条/细长平面 */
import * as THREE from 'three'

export function createWeather(scene, opts = {}) {
  const count = opts.count || 800
  const area = opts.area || 120
  
  // 雨滴用 LineSegments 更高效
  const geo = new THREE.BufferGeometry()
  const pos = new Float32Array(count * 6) // 每滴 2 个点
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  const mat = new THREE.LineBasicMaterial({
    color: 0x8fb8d8, transparent: true, opacity: 0.5,
  })
  const lines = new THREE.LineSegments(geo, mat)
  lines.frustumCulled = false
  lines.visible = false
  scene.add(lines)

  const drops = []
  for (let i = 0; i < count; i++) {
    drops.push({
      x: (Math.random() - 0.5) * area,
      y: Math.random() * 30 + 5,
      z: (Math.random() - 0.5) * area,
      speed: 18 + Math.random() * 8,
    })
  }

  let enabled = false
  let centerX = 0, centerZ = 0

  function update(dt) {
    if (!enabled) return
    const p = geo.attributes.position.array
    for (let i = 0; i < count; i++) {
      const d = drops[i]
      d.y -= d.speed * dt
      // 落地或太远则重置到顶部
      if (d.y < 0) {
        d.y = 25 + Math.random() * 10
        d.x = centerX + (Math.random() - 0.5) * area
        d.z = centerZ + (Math.random() - 0.5) * area
      }
      // 线段：从 (x,y,z) 到 (x, y+0.7, z) - 雨滴拖尾
      const i6 = i * 6
      p[i6] = d.x; p[i6 + 1] = d.y; p[i6 + 2] = d.z
      p[i6 + 3] = d.x; p[i6 + 4] = d.y + 0.7; p[i6 + 5] = d.z
    }
    geo.attributes.position.needsUpdate = true
  }

  return {
    update,
    setEnabled(v) {
      enabled = v
      lines.visible = v
    },
    setCenter(x, z) { centerX = x; centerZ = z },
    isEnabled: () => enabled,
  }
}
