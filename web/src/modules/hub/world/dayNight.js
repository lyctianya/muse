/* 日夜循环：原站 Lighting/day-night 的 WebGL 实现
   - 太阳沿轨道运行，颜色/强度随高度变化
   - 天空/雾颜色同步，日出日落暖色，正午白，夜晚深蓝
   - 可调速度，默认一局 4 分钟一昼夜 */
import * as THREE from 'three'

export function createDayNight(scene, sun, hemi, opts = {}) {
  const dayLength = opts.dayLength || 240 // 秒/昼夜
  let time = opts.startTime || 0.3 // 0-1，0.3=上午
  let enabled = true
  let speed = 1

  // 月亮（简单球体）
  const moon = new THREE.Mesh(
    new THREE.SphereGeometry(3, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xe8ecff, fog: false })
  )
  moon.visible = false
  scene.add(moon)

  // 星星
  const starGeo = new THREE.BufferGeometry()
  const starPos = new Float32Array(300 * 3)
  for (let i = 0; i < 300; i++) {
    const r = 280, th = Math.random() * Math.PI * 2, ph = Math.random() * Math.PI * 0.5
    starPos[i * 3] = r * Math.sin(ph) * Math.cos(th)
    starPos[i * 3 + 1] = r * Math.cos(ph) + 20
    starPos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th)
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3))
  const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 1.2, sizeAttenuation: false, fog: false, transparent: true, opacity: 0 })
  const stars = new THREE.Points(starGeo, starMat)
  scene.add(stars)

  const skyDay = new THREE.Color(0x87ceeb)
  const skySunset = new THREE.Color(0xff8c42)
  const skyNight = new THREE.Color(0x0a0e2a)
  const tmpSky = new THREE.Color()
  const tmpFog = new THREE.Color()

  function update(dt) {
    if (!enabled) return
    time = (time + (dt / dayLength) * speed) % 1

    // 太阳角度：time=0.25 日出，0.5 正午，0.75 日落
    const sunAngle = (time - 0.25) * Math.PI * 2
    const sunH = Math.sin(sunAngle) // 高度 -1~1
    const sunA = Math.cos(sunAngle)

    // 太阳位置
    const R = 80
    sun.position.set(sunA * R, Math.max(sunH, -0.2) * R, 30)
    
    // 太阳强度/颜色
    if (sunH > 0) {
      // 白天
      const noon = Math.min(sunH * 2, 1) // 正午=1
      sun.intensity = 0.3 + noon * 2.5
      // 日出日落暖色
      const warm = Math.max(0, 1 - sunH * 3)
      sun.color.setHex(0xfff1d6).lerp(new THREE.Color(0xff6b35), warm * 0.8)
      sun.visible = true
      moon.visible = false
    } else {
      // 夜晚：太阳关闭，月亮升起
      sun.intensity = 0
      sun.visible = false
      moon.visible = true
      const moonH = -sunH
      moon.position.set(-sunA * R, Math.max(moonH, 0.1) * R, -30)
    }

    // 半球光
    hemi.intensity = sunH > 0 ? 0.4 + Math.min(sunH * 2, 1) * 1.2 : 0.15

    // 天空颜色
    if (sunH > 0.3) {
      tmpSky.copy(skyDay)
    } else if (sunH > 0) {
      const t = sunH / 0.3
      tmpSky.copy(skySunset).lerp(skyDay, t)
    } else if (sunH > -0.2) {
      const t = -sunH / 0.2
      tmpSky.copy(skySunset).lerp(skyNight, t)
    } else {
      tmpSky.copy(skyNight)
    }
    scene.background = tmpSky
    if (scene.fog) {
      tmpFog.copy(tmpSky).multiplyScalar(0.9)
      scene.fog.color.copy(tmpFog)
    }

    // 星星
    const nightness = sunH < 0 ? Math.min(-sunH * 3, 1) : 0
    starMat.opacity = nightness * 0.9
    stars.visible = nightness > 0.01
  }

  return {
    update,
    setEnabled(v) { enabled = v },
    setSpeed(s) { speed = s },
    setTime(t) { time = t % 1 },
    getTime: () => time,
    // 白天=0.5附近
    isDay: () => { const a = (time - 0.25) * Math.PI * 2; return Math.sin(a) > 0 },
  }
}
