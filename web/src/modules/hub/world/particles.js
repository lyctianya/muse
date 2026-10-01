/* 尘土/烟雾粒子池：Sprite 复用 */
import { puffTexture } from './textures.js'

export async function createParticles(scene, max = 48) {
  const THREE = await import('three')
  const tex = await puffTexture()
  const pool = []
  for (let i = 0; i < max; i++) {
    const m = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0, depthWrite: false })
    const s = new THREE.Sprite(m)
    s.visible = false
    scene.add(s)
    pool.push({ s, life: 0, maxLife: 1, vx: 0, vy: 0, vz: 0, grow: 1, fade: 1 })
  }
  let cursor = 0

  function spawn(x, y, z, opts = {}) {
    const p = pool[cursor]
    cursor = (cursor + 1) % pool.length
    p.s.visible = true
    p.s.position.set(x, y, z)
    p.life = p.maxLife = opts.life || 0.8
    p.vx = opts.vx ?? (Math.random() - 0.5) * 1.5
    p.vy = opts.vy ?? (1 + Math.random() * 1.5)
    p.vz = opts.vz ?? (Math.random() - 0.5) * 1.5
    p.grow = opts.grow || 2.2
    const size = opts.size || 0.8
    p.s.scale.set(size, size, 1)
    p.s.material.opacity = opts.opacity ?? 0.55
    p.s.material.color.set(opts.color || 0xd8cfc0)
    p.fade = p.s.material.opacity
  }

  function burst(x, y, z, n = 6, opts = {}) {
    for (let i = 0; i < n; i++) spawn(x, y, z, opts)
  }

  function update(dt) {
    for (const p of pool) {
      if (!p.s.visible) continue
      p.life -= dt
      if (p.life <= 0) { p.s.visible = false; continue }
      const k = p.life / p.maxLife
      p.s.position.x += p.vx * dt
      p.s.position.y += p.vy * dt
      p.s.position.z += p.vz * dt
      p.vy *= 1 - 0.6 * dt
      const sc = p.s.scale.x + p.grow * dt
      p.s.scale.set(sc, sc, 1)
      p.s.material.opacity = p.fade * k
    }
  }

  return { spawn, burst, update }
}
