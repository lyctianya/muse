/* 吉普车：bruno-simon.com 原站模型（MIT，见 /hub/ATTRIBUTION.md）
   + Rapier 街机物理控制器 */
import { loadJeep } from './brunoAssets.js'
import { honkTexture } from './textures.js'

const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

/* 原站模型：车头朝 +X，单个 wheelContainer 模板需克隆出 4 个轮子 */
export async function buildJeep() {
  const THREE = await import('three')
  const { root, wheelTemplate } = await loadJeep()

  const carrier = new THREE.Group() // 位置 + 朝向（+Z 为前）
  const tilt = new THREE.Group()     // 悬挂/倾斜
  const align = new THREE.Group()    // 模型空间 → 世界：转朝向 + 落地
  align.rotation.y = -Math.PI / 2    // +X → +Z
  carrier.add(tilt)
  tilt.add(align)
  for (const child of [...root.children]) align.add(child)

  // 4 个轮子：前轮 x=+0.87（模型空间）
  const WHEEL_X = 0.87, WHEEL_Y = -0.42, WHEEL_Z = 0.70
  const wheels = []
  if (!wheelTemplate) console.warn('[hub] wheelContainer 模板未找到，轮子将缺失')
  // 移除原模板（后面用克隆重建 4 个）
  if (wheelTemplate && wheelTemplate.parent) wheelTemplate.parent.remove(wheelTemplate)
  const defs = [
    [WHEEL_X, -WHEEL_Z, true], [WHEEL_X, WHEEL_Z, true],
    [-WHEEL_X, -WHEEL_Z, false], [-WHEEL_X, WHEEL_Z, false],
  ]
  for (const [sx, sz, front] of defs) {
    const steer = new THREE.Group()
    steer.position.set(sx, WHEEL_Y, sz)
    // 转动件：wheel.006 / wheelPainted（转轴为模型 Z 向）
    const spinMeshes = []
    if (wheelTemplate) {
      const wc = wheelTemplate.clone(true)
      wc.position.set(0, 0, 0)
      steer.add(wc)
      wc.traverse((o) => {
        if (o.isMesh && (o.name.startsWith('wheel.') || o.name === 'wheelPainted')) spinMeshes.push(o)
      })
    }
    align.add(steer)
    wheels.push({ steer, spinMeshes, front })
  }

  // 落地：包围盒底面对齐 y=0
  align.updateWorldMatrix(true, true)
  const bbox = new THREE.Box3().setFromObject(align)
  align.position.y = -bbox.min.y

  // 喇叭气泡
  const bubble = new THREE.Sprite(new THREE.SpriteMaterial({
    map: await honkTexture(), transparent: true, depthWrite: false,
  }))
  bubble.scale.set(1.6, 1.2, 1)
  bubble.position.set(0, 3.4, 0.6)
  bubble.visible = false
  carrier.add(bubble)

  return { carrier, tilt, wheels, bubble }
}

/* 街机手感：速度/转向直接驱动，碰撞交给 Rapier
   返回事件 { jumped, landed, crashed } */
export function createCar(RAPIER, world, parts, spawn = { x: 0, y: 0.6, z: 11, yaw: Math.PI }) {
  const body = world.createRigidBody(
    RAPIER.RigidBodyDesc.dynamic()
      .setTranslation(spawn.x, spawn.y, spawn.z)
      .setLinearDamping(0.05)
      .setAngularDamping(1.5)
  )
  world.createCollider(
    RAPIER.ColliderDesc.cuboid(0.95, 0.7, 1.9)
      .setTranslation(0, 0.8, 0)
      .setFriction(0.7)
      .setRestitution(0.05),
    body
  )

  const S = { yaw: spawn.yaw, speed: 0, bounce: 0, wasAirborne: false, crashCool: 0 }
  const prevPos = { x: spawn.x, z: spawn.z }

  function step(dt, input) {
    const ev = { jumped: false, landed: false, crashed: false }
    const max = input.boost ? 32 : 20
    if (input.throttle) S.speed += input.throttle * 15 * dt
    S.speed -= S.speed * 1.7 * dt            // 阻力
    if (input.brake) S.speed -= S.speed * 7 * dt // 刹车
    S.speed = clamp(S.speed, -5, max)
    const grip = clamp(Math.abs(S.speed) / 3.5, 0, 1)
    S.yaw -= input.steer * 2.1 * grip * (S.speed >= 0 ? 1 : -1) * dt

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
      if (w.front) w.steer.rotation.y = -input.steer * 0.5
      for (const m of w.spinMeshes) m.rotation.z -= (S.speed * dt) / 0.43
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
    S.yaw = spawn.yaw; S.speed = 0; S.wasAirborne = false
    prevPos.x = spawn.x; prevPos.z = spawn.z
    body.setTranslation({ x: spawn.x, y: spawn.y, z: spawn.z }, true)
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
