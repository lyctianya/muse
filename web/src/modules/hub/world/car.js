/* 玩具吉普：外观（代码建模） + Rapier 街机物理控制器 */
import { PALETTE } from './palette.js'

const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

export async function buildJeep() {
  const THREE = await import('three')
  const mat = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.7, metalness: 0.1, ...o })
  const box = (w, h, d, c, x = 0, y = 0, z = 0, o = {}) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(c, o))
    m.position.set(x, y, z)
    m.castShadow = true
    return m
  }

  const carrier = new THREE.Group() // 位置 + 朝向
  const tilt = new THREE.Group()     // 加速/转向倾斜
  carrier.add(tilt)

  tilt.add(box(1.7, 0.45, 2.9, PALETTE.red, 0, 0.72, 0))            // 车身
  tilt.add(box(1.74, 0.16, 0.5, PALETTE.redDark, 0, 0.6, 1.45))     // 前杠
  tilt.add(box(1.5, 0.62, 1.35, PALETTE.white, 0, 1.22, -0.35))    // 座舱
  const shield = box(1.34, 0.42, 0.07, PALETTE.glass, 0, 1.28, 0.36, { roughness: 0.15, metalness: 0.3 })
  shield.rotation.x = -0.18
  tilt.add(shield)                                                  // 风挡
  tilt.add(box(0.5, 0.5, 0.5, PALETTE.dark, -0.4, 1.08, -0.4))     // 座椅
  tilt.add(box(0.5, 0.5, 0.5, PALETTE.dark, 0.4, 1.08, -0.4))
  for (const sx of [-0.55, 0.55]) {                                // 车灯
    const lamp = new THREE.Mesh(
      new THREE.SphereGeometry(0.13, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0xfff4c2 })
    )
    lamp.position.set(sx, 0.85, 1.47)
    tilt.add(lamp)
  }

  // 轮子：steer(转向) > spin(滚动) > 网格
  const wheels = []
  const wheelGeo = new THREE.CylinderGeometry(0.44, 0.44, 0.36, 14)
  const hubGeo = new THREE.CylinderGeometry(0.2, 0.2, 0.38, 10)
  const defs = [
    [-0.98, 1.02, true], [0.98, 1.02, true],
    [-0.98, -1.02, false], [0.98, -1.02, false],
  ]
  for (const [sx, sz, front] of defs) {
    const steer = new THREE.Group()
    steer.position.set(sx, 0.44, sz)
    const spin = new THREE.Group()
    const wm = new THREE.Mesh(wheelGeo, mat(0x1a1a1a, { roughness: 0.95 }))
    wm.rotation.z = Math.PI / 2
    wm.castShadow = true
    const hub = new THREE.Mesh(hubGeo, mat(0xf2f2f2, { roughness: 0.4 }))
    hub.rotation.z = Math.PI / 2
    spin.add(wm); spin.add(hub)
    steer.add(spin); tilt.add(steer)
    wheels.push({ steer, spin, front })
  }
  return { carrier, tilt, wheels }
}

/* 街机手感：速度/转向直接驱动，碰撞交给 Rapier */
export function createCar(RAPIER, world, parts) {
  const body = world.createRigidBody(
    RAPIER.RigidBodyDesc.dynamic()
      .setTranslation(0, 0.6, 11)
      .setLinearDamping(0.05)
      .setAngularDamping(1.5)
  )
  world.createCollider(
    RAPIER.ColliderDesc.cuboid(0.85, 0.55, 1.45)
      .setTranslation(0, 0.75, 0)
      .setFriction(0.7)
      .setRestitution(0.05),
    body
  )

  const S = { yaw: Math.PI, speed: 0 } // 出生朝中心（-Z）

  function step(dt, input) {
    const max = input.boost ? 17 : 11
    if (input.throttle) S.speed += input.throttle * 15 * dt
    S.speed -= S.speed * 1.7 * dt            // 阻力
    if (input.brake) S.speed -= S.speed * 7 * dt // 刹车
    S.speed = clamp(S.speed, -5, max)
    const grip = clamp(Math.abs(S.speed) / 3.5, 0, 1)
    S.yaw += input.steer * 2.1 * grip * (S.speed >= 0 ? 1 : -1) * dt

    const fx = Math.sin(S.yaw), fz = Math.cos(S.yaw)
    const v = body.linvel()
    body.setLinvel({ x: fx * S.speed, y: v.y, z: fz * S.speed }, true)
    const h = S.yaw / 2
    body.setRotation({ x: 0, y: Math.sin(h), z: 0, w: Math.cos(h) }, true)
    body.setAngvel({ x: 0, y: 0, z: 0 }, true) // 保持不翻车

    // 世界边界
    const p = body.translation()
    const r = Math.hypot(p.x, p.z)
    if (r > 36) {
      const k = 36 / r
      body.setTranslation({ x: p.x * k, y: p.y, z: p.z * k }, true)
      S.speed *= 0.5
    }

    parts.carrier.position.set(p.x, Math.max(0, p.y), p.z)
    parts.carrier.rotation.y = S.yaw
    for (const w of parts.wheels) {
      if (w.front) w.steer.rotation.y = input.steer * 0.5
      w.spin.rotation.x += (S.speed * dt) / 0.44
    }
    parts.tilt.rotation.z = -input.steer * clamp(Math.abs(S.speed) / 11, 0, 1) * 0.07
    parts.tilt.rotation.x = clamp(-input.throttle * 0.03, -0.05, 0.05)
  }

  function respawn() {
    S.yaw = Math.PI; S.speed = 0
    body.setTranslation({ x: 0, y: 0.6, z: 11 }, true)
    body.setLinvel({ x: 0, y: 0, z: 0 }, true)
    body.setAngvel({ x: 0, y: 0, z: 0 }, true)
  }

  return {
    step, respawn,
    get pos() { return body.translation() },
    get yaw() { return S.yaw },
    get speed() { return S.speed },
  }
}
