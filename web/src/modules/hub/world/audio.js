/* 原站真实音效（MIT，见 /hub/ATTRIBUTION.md）
   engine/honk/rolling/hit 来自 bruno-simon.com，music 为 Kounine CC0 */
let engine = null
let rolling = null
let music = null
let muted = false
let ready = false

function makeAudio(src, loop = false, volume = 1) {
  const a = new Audio(src)
  a.loop = loop
  a.volume = volume
  a.preload = 'auto'
  return a
}

/* 必须在用户手势中调用 */
export function initAudio() {
  if (ready) return
  ready = true
  try {
    engine = makeAudio('/hub/sounds/engine.mp3', true, 0)
    rolling = makeAudio('/hub/sounds/rolling.mp3', true, 0)
    music = makeAudio('/hub/sounds/music.mp3', true, 0.32)
    // 预热播放（手势内允许）
    engine.play().catch(() => {})
    rolling.play().catch(() => {})
    music.play().catch(() => {})
  } catch (e) {
    console.warn('音频初始化失败', e)
  }
}

/* 每帧调用：speed01 0~1 */
export function engineUpdate(speed01, boosting, active) {
  if (!ready || !engine) return
  const on = active && !muted
  engine.volume = on ? 0.12 + speed01 * 0.30 : 0
  engine.playbackRate = 0.75 + speed01 * 0.9 + (boosting ? 0.25 : 0)
  rolling.volume = on ? speed01 * 0.35 : 0
  rolling.playbackRate = 0.8 + speed01 * 0.6
}

function oneShot(src, volume = 0.5) {
  if (!ready || muted) return
  try {
    const a = makeAudio(src, false, volume)
    a.play().catch(() => {})
  } catch (e) { /* ignore */ }
}

export function honk() { oneShot('/hub/sounds/honk.mp3', 0.55) }
export function hit() { oneShot('/hub/sounds/hit.mp3', 0.6) }

/* 成就提示音：简单的合成 ding（原站无单文件，保留合成） */
let actx = null
export function ding() {
  if (!ready || muted) return
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)()
    const t = actx.currentTime
    for (const [f, d] of [[880, 0], [1318, 0.12]]) {
      const o = actx.createOscillator(), g = actx.createGain()
      o.type = 'sine'; o.frequency.value = f
      g.gain.setValueAtTime(0.18, t + d)
      g.gain.exponentialRampToValueAtTime(0.001, t + d + 0.4)
      o.connect(g); g.connect(actx.destination)
      o.start(t + d); o.stop(t + d + 0.45)
    }
  } catch (e) { /* ignore */ }
}

export function boing() {
  if (!ready || muted) return
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)()
    const t = actx.currentTime
    const o = actx.createOscillator(), g = actx.createGain()
    o.type = 'sine'
    o.frequency.setValueAtTime(220, t)
    o.frequency.exponentialRampToValueAtTime(520, t + 0.22)
    g.gain.setValueAtTime(0.15, t)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.28)
    o.connect(g); g.connect(actx.destination)
    o.start(t); o.stop(t + 0.3)
  } catch (e) { /* ignore */ }
}

export function thud() { hit() }

export function toggleMute() {
  muted = !muted
  if (music) music.volume = muted ? 0 : 0.32
  return muted
}
export function isMuted() { return muted }
