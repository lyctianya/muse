/* 玩具吉普：外观（代码建模） + Rapier 街机物理控制器 */
import { PALETTE } from './palette.js'
import { honkTexture } from './textures.js'

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
  const tilt = new THREE.Group()     // 加速/转向倾斜 + 悬挂
  carrier.add(tilt)

  tilt.add(box(1.7, 0.45, 2.9, PALETTE.red, 0, 0.72, 0))            // 车身
  tilt.add(box(1.74, 0.16, 0.5, PALETTE.redDark, 0, 0.6, 1.45))     // 前杠
  tilt.add(box(1.5, 0.62, 1.35, PALETTE.white, 0, 1.22, -0.35))    // 座舱
  const shield = box(1.34, 0.42, 0.07, PALETTE.glass, 0, 1.28, 0.36, { roughness: 0.15, metalness: 0.3 })
  shield.rotation.x = -0.18
  tilt.add(shield)                                                  // 风挡
  tilt.add(box(0.5, 0.5, 0.5, PALETTE.dark, -0.4, 1.08, -0.4))     // 座椅
  tilt.add(box(0.5, 0.5, 0.5, PALETTE.dark, 0.4, 1.08, -0.4))

  // 司机
  tilt.add(box(0.52, 0.55, 0.38, PALETTE.teal, 0.4, 1.62, -0.4))  // 躯干
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.21, 12, 12), mat(0xffd9b3))
  head.position.set(0.4, 2.05, -0.4)
  head.castShadow = true
  tilt.add(head)
  tilt.add(box(0.5, 0.1, 0.5, PALETTE.gold, 0.4, 2.22, -0.4))      // 帽子
  tilt.add(box(0.62, 0.05, 0.2, PALETTE.gold, 0.4, 2.18, -0.12))   // 帽檐
  const armL = box(0.14, 0.14, 0.55, PALETTE.teal, 0.4, 1.72, 0.05)
  armL.rotation.x = -0.5
  tilt.add(armL)                                                    // 手搭方向盘
  const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.05, 8, 16), mat(PALETTE.dark))
  wheel.position.set(0.4, 1.62, 0.28)
  wheel.rotation.x = -0.9
  tilt.add(wheel)

  for (const sx of [-0.55, 0.55]) {                                // 车灯
    const lamp = new THREE.Mesh(
      new THREE.SphereGeometry(0.13, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0xfff4c2 })
    )
    lamp.position.set(sx, 0.85, 1.47)
    tilt.add(lamp)
  }
  // 备胎
  const spare = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.15, 8, 18), mat(0x1a1a1a, { roughness: 0.95 }))
  spare.position.set(0, 0.95, -1.52)
  spare.castShadow = true
  tilt.add(spare)
  // 排气管
  const exhaust = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.5, 8), mat(0x8a8f98, { metalness: 0.6, roughness: 0.35 }))
  exhaust.rotation.x = Math.PI / 2
  exhaust.position.set(-0.6, 0.45, -1.6)
  tilt.add(exhaust)

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
    // 挡泥板
    tilt.add(box(0.56, 0.1, 1.05, PALETTE.redDark, sx, 0.98, sz))
    wheels.push({ steer, spin, front })
  }

  // 喇叭气泡
  const bubble = new THREE.Sprite(new THREE.SpriteMaterial({
    map: await honkTexture(), transparent: true, depthWrite: false,
  }))
  bubble.scale.set(1.6, 1.2, 1)
  bubble.position.set(0, 3.1, 0.6)
  bubble.visible = false
  carrier.add(bubble)

  return { carrier, tilt, wheels, bubble }
}

/* 街机手感：速度/转向直接驱动，碰撞交给 Rapier
   返回事件 { jumped, landed, crashed } */
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

  const S = { yaw: Math.PI, speed: 0, bounce: 0, wasAirborne: false, crashCool: 0 }
  const prevPos = { x: 0, z: 11 }

  function step(dt, input) {
    const ev = { jumped: false, landed: false, crashed: false }
    const max = input.boost ? 17 : 11
    if (input.throttle) S.speed += input.throttle * 15 * dt
    S.speed -= S.speed * 1.7 * dt            // 阻力
    if (input.brake) S.speed -= S.speed * 7 * dt // 刹车
    S.speed = clamp(S.speed, -5, max)
    const grip = clamp(Math.abs(S.speed) / 3.5, 0, 1)
    S.yaw += input.steer * 2.1 * grip * (S.speed >= 0 ? 1 : -1) * dt

    // 跳跃（空格）：只在贴地时触发
    const p0 = body.translation()
    const v0 = body.linvel()
    let vy = v0.y
    if (input.jump) {
      input.jump = false
      if (p0.y < 0.15 && Math.abs(v0.y) < 1) {
        vy = 7.4
        ev.jumped = true
      }
    }

    const fx = Math.sin(S.yaw), fz = Math.cos(S.yaw)
    body.setLinvel({ x: fx * S.speed, y: vy, z: fz * S.speed }, true)
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

    // 撞车检测：想走的 vs 实际走的
    const intended = Math.abs(S.speed) * dt
    const actual = Math.hypot(p.x - prevPos.x, p.z - prevPos.z)
    prevPos.x = p.x; prevPos.z = p.z
    S.crashCool = Math.max(0, S.crashCool - dt)
    if (Math.abs(S.speed) > 5 && intended > 0.01 && actual < intended * 0.3 && S.crashCool <= 0) {
      ev.crashed = true
      S.crashCool = 1.2
      S.speed *= 0.35
    }

    // 落地检测
    const airborne = p.y > 0.6
    if (S.wasAirborne && !airborne && p.y < 0.15) ev.landed = true
    S.wasAirborne = airborne

    parts.carrier.position.set(p.x, Math.max(0, p.y), p.z)
    parts.carrier.rotation.y = S.yaw
    for (const w of parts.wheels) {
      if (w.front) w.steer.rotation.y = input.steer * 0.5
      w.spin.rotation.x += (S.speed * dt) / 0.44
    }
    // 悬挂起伏 + 加速/转向倾斜
    S.bounce += dt * (5 + Math.abs(S.speed) * 1.4)
    const ride = clamp(Math.abs(S.speed) / 11, 0, 1)
    parts.tilt.position.y = Math.abs(Math.sin(S.bounce)) * 0.07 * ride + (airborne ? 0.12 : 0)
    parts.tilt.rotation.z = -input.steer * ride * 0.07
    parts.tilt.rotation.x = clamp(-input.throttle * 0.03, -0.05, 0.05) + (airborne ? -0.1 : 0)
    return ev
  }

  function respawn() {
    S.yaw = Math.PI; S.speed = 0; S.wasAirborne = false
    prevPos.x = 0; prevPos.z = 11
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
