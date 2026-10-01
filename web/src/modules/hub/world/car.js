/* 吉普车：bruno-simon.com 原站模型（MIT，见 /hub/ATTRIBUTION.md）
   + Rapier 街机物理控制器 */
import { loadJeep } from './brunoAssets.js'
import { honkTexture } from './textures.js'

const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

/* 车漆：原站 VisualVehicle.setPaints 6 种（红/橙/白/黑/火焰/深渊）
   渐变用纵向 Canvas 纹理，火焰/深渊用简化 Shader */
function createPaints(THREE) {
  const paints = {}
  const grad = (name, cA, cB) => {
    const cv = document.createElement('canvas')
    cv.width = 1; cv.height = 64
    const ctx = cv.getContext('2d')
    const g = ctx.createLinearGradient(0, 0, 0, 64)
    g.addColorStop(0, cA); g.addColorStop(1, cB)
    ctx.fillStyle = g; ctx.fillRect(0, 0, 1, 64)
    const tex = new THREE.CanvasTexture(cv)
    tex.colorSpace = THREE.SRGBColorSpace
    const m = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.35, metalness: 0.1 })
    paints[name] = m
    return m
  }
  grad('red', '#ff3a3a', '#721551')
  grad('orange', '#ff940d', '#af0071')
  grad('white', '#ffffff', '#b5b5b5')
  grad('black', '#626262', '#262526')
  // 火焰：橙红噪声动画（简化版）
  const flameMat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform float time; varying vec2 vUv;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
        return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }
      void main() {
        vec2 uv = vUv * vec2(3.0, 1.5);
        uv.y += time * 0.8;
        float n = noise(uv) * 0.6 + noise(uv*2.3) * 0.4;
        float flame = smoothstep(0.3, 0.9, n + (1.0 - vUv.y) * 0.4);
        vec3 col = mix(vec3(1.0, 0.61, 0.13), vec3(1.0, 0.0, 0.0), vUv.y);
        col = mix(vec3(0.4, 0.05, 0.2), col, flame);
        // 发光
        col *= 1.0 + flame * 2.0;
        gl_FragColor = vec4(col, 1.0);
      }`,
  })
  paints.flames = flameMat
  // 深渊：深蓝紫 + 菲涅尔（简化版）
  const abyssMat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 } },
    vertexShader: `varying vec3 vN; varying vec3 vV; varying vec2 vUv;
      void main() { vUv = uv; vN = normalize(normalMatrix * normal);
        vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `
      uniform float time; varying vec3 vN; varying vec3 vV; varying vec2 vUv;
      void main() {
        float fres = pow(1.0 - abs(dot(vN, vV)), 2.0);
        vec3 col = mix(vec3(0.05, 0.03, 0.15), vec3(0.38, 0.33, 1.0), fres);
        // 星点
        vec2 sp = floor(vUv * 40.0);
        float star = step(0.97, fract(sin(dot(sp, vec2(12.9898,78.233))) * 43758.5453));
        col += vec3(1.0) * star * 0.8;
        gl_FragColor = vec4(col, 1.0);
      }`,
  })
  paints.abyssal = abyssMat
  return paints
}

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

  // 4 个轮子：照原站 VisualVehicle.setWheels（offset x=0.90 z=0.75，+z 侧转 PI 镜像）
  const WHEEL_X = 0.90, WHEEL_Y = -0.42, WHEEL_Z = 0.75
  const wheels = []
  if (!wheelTemplate) console.warn('[hub] wheelContainer 模板未找到，轮子将缺失')
  // 移除原模板（后面用克隆重建 4 个）
  if (wheelTemplate && wheelTemplate.parent) wheelTemplate.parent.remove(wheelTemplate)
  // 顺序：前左(-z)/前右(+z)/后左(-z)/后右(+z)；+z 侧（右）需绕 Y 转 PI 镜像
  const defs = [
    [WHEEL_X, -WHEEL_Z, true, false], [WHEEL_X, WHEEL_Z, true, true],
    [-WHEEL_X, -WHEEL_Z, false, false], [-WHEEL_X, WHEEL_Z, false, true],
  ]
  for (const [sx, sz, front, mirror] of defs) {
    const steer = new THREE.Group()
    steer.position.set(sx, WHEEL_Y, sz)
    // 转动件：wheel.006 / wheelPainted（转轴为模型 Z 向）
    const spinMeshes = []
    if (wheelTemplate) {
      const wc = wheelTemplate.clone(true)
      wc.position.set(0, 0, 0)
      if (mirror) wc.rotation.y = Math.PI
      steer.add(wc)
      wc.traverse((o) => {
        if (o.isMesh && (o.name.startsWith('wheel.') || o.name === 'wheelPainted')) spinMeshes.push(o)
      })
    }
    align.add(steer)
    wheels.push({ steer, spinMeshes, front, mirror })
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

  // 车灯/能量格（原站 VisualVehicle.setBlinkers/setBackLights/setBoostAnimation）
  const findPart = (re) => {
    let found = null
    align.traverse((o) => { if (!found && re.test(o.name || '')) found = o })
    return found
  }
  const blinkerLeft = findPart(/^blinkerLeft/i)
  const blinkerRight = findPart(/^blinkerRight/i)
  const stopLights = findPart(/^stopLights/i)
  const backLights = findPart(/^backLights/i)
  const cells = [findPart(/^cell1/i), findPart(/^cell2/i), findPart(/^cell3/i)].filter(Boolean)
  if (blinkerLeft) blinkerLeft.visible = false
  if (blinkerRight) blinkerRight.visible = false
  if (stopLights) stopLights.visible = false
  if (backLights) backLights.visible = false
  // 能量格初始位置（用于加速动画）
  const cellBaseY = cells.map((c) => c.position.y)

  // 车漆系统（原站 VisualVehicle.setPaints）
  const paints = createPaints(THREE)
  const bodyPainted = findPart(/^bodyPainted/i)
  // 收集所有 wheelPainted（4 个轮子的轮毂）
  const wheelPainteds = []
  align.traverse((o) => { if (/^wheelPainted/i.test(o.name || '')) wheelPainteds.push(o) })
  let currentPaint = 'red'
  const setPaint = (name) => {
    if (!paints[name]) return false
    currentPaint = name
    const mat = paints[name]
    if (bodyPainted) bodyPainted.material = mat
    for (const wp of wheelPainteds) wp.material = mat
    return true
  }
  setPaint('red')

  return { carrier, tilt, wheels, bubble, blinkerLeft, blinkerRight, stopLights, backLights, cells, cellBaseY, paints, setPaint, getPaint: () => currentPaint }
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
      // 镜像轮（+z 侧）转轴反向，需反转自转方向（照原站 VisualVehicle.update）
      const dir = w.mirror ? 1 : -1
      for (const m of w.spinMeshes) m.rotation.z += dir * (S.speed * dt) / 0.43
    }
    // 车灯：转向灯闪烁 / 刹车灯 / 倒车灯（原站 VisualVehicle）
    const t = performance.now() / 1000
    const blinkOn = Math.sin(t * 10) > 0
    if (parts.blinkerLeft) parts.blinkerLeft.visible = input.steer < -0.1 && blinkOn
    if (parts.blinkerRight) parts.blinkerRight.visible = input.steer > 0.1 && blinkOn
    if (parts.stopLights) parts.stopLights.visible = !!input.brake
    if (parts.backLights) parts.backLights.visible = S.speed < -0.5
    // 车漆 shader 时间更新（火焰/深渊动画）
    if (parts.paints) {
      for (const k of ['flames', 'abyssal']) {
        if (parts.paints[k] && parts.paints[k].uniforms) {
          parts.paints[k].uniforms.time.value = t
        }
      }
    }
    // 能量格：加速时上下浮动（原站 setBoostAnimation）
    if (parts.cells && parts.cells.length) {
      const boost = input.boost ? 1 : 0
      parts.cells.forEach((c, i) => {
        c.position.y = parts.cellBaseY[i] + Math.sin(t * 8 + i * 2.1) * 0.08 * boost
      })
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
    setPaint: parts.setPaint,
    getPaint: parts.getPaint,
  }
}

/* 轮胎印：原站 Track 简化版 —— 车轮位置留下渐隐深色印记 */
export function createTireTracks(THREE, scene, maxTracks = 200) {
  const geo = new THREE.PlaneGeometry(0.28, 0.7)
  const mat = new THREE.MeshBasicMaterial({
    color: 0x1a1a1a, transparent: true, opacity: 0.5,
    depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1,
  })
  const tracks = []
  let idx = 0
  // 预分配
  const meshes = []
  for (let i = 0; i < maxTracks; i++) {
    const m = new THREE.Mesh(geo, mat.clone())
    m.rotation.x = -Math.PI / 2
    m.visible = false
    m.renderOrder = 1
    scene.add(m)
    meshes.push(m)
  }
  return {
    // 在世界坐标 (x, z) 留印，yaw 为车朝向
    add(x, z, yaw, groundY = 0.02) {
      const m = meshes[idx]
      idx = (idx + 1) % maxTracks
      m.position.set(x, groundY, z)
      m.rotation.z = -yaw
      m.material.opacity = 0.5
      m.visible = true
      tracks.push({ mesh: m, life: 1 })
      if (tracks.length > maxTracks) tracks.shift()
    },
    update(dt) {
      for (let i = tracks.length - 1; i >= 0; i--) {
        const t = tracks[i]
        t.life -= dt / 8 // 8 秒渐隐
        if (t.life <= 0) {
          t.mesh.visible = false
          tracks.splice(i, 1)
        } else {
          t.mesh.material.opacity = 0.5 * t.life
        }
      }
    },
  }
}
