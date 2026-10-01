/* 程序化 WebAudio：引擎轰鸣 + 喇叭 + 音效，无外部音频文件 */
let ctx = null
let master = null
let eng = null

export function initAudio() {
  if (ctx) { if (ctx.state === 'suspended') ctx.resume(); return }
  const AC = window.AudioContext || window.webkitAudioContext
  if (!AC) return
  ctx = new AC()
  master = ctx.createGain()
  master.gain.value = 0.35
  master.connect(ctx.destination)
  // 引擎：锯齿 + 方波 → 低通
  const o1 = ctx.createOscillator(); o1.type = 'sawtooth'; o1.frequency.value = 55
  const o2 = ctx.createOscillator(); o2.type = 'square'; o2.frequency.value = 28
  const filt = ctx.createBiquadFilter(); filt.type = 'lowpass'; filt.frequency.value = 320
  const g = ctx.createGain(); g.gain.value = 0
  o1.connect(filt); o2.connect(filt); filt.connect(g); g.connect(master)
  o1.start(); o2.start()
  eng = { o1, o2, g }
}

export function engineUpdate(speed01, boosting, active) {
  if (!ctx || !eng) return
  const t = ctx.currentTime
  eng.o1.frequency.setTargetAtTime(55 + speed01 * 120 + (boosting ? 35 : 0), t, 0.06)
  eng.o2.frequency.setTargetAtTime(28 + speed01 * 60, t, 0.06)
  eng.g.gain.setTargetAtTime(active ? 0.05 + speed01 * 0.07 : 0, t, 0.12)
}

function blip(freqA, freqB, dur, type = 'square', vol = 0.16) {
  if (!ctx) return
  const t = ctx.currentTime
  const o = ctx.createOscillator(), g = ctx.createGain()
  o.type = type
  o.frequency.setValueAtTime(freqA, t)
  o.frequency.setValueAtTime(freqB, t + dur * 0.4)
  g.gain.setValueAtTime(vol, t)
  g.gain.exponentialRampToValueAtTime(0.001, t + dur)
  o.connect(g); g.connect(master)
  o.start(t); o.stop(t + dur + 0.02)
}

export function honk() { blip(540, 400, 0.28, 'square', 0.14) }
export function ding() {
  blip(880, 880, 0.35, 'sine', 0.2)
  setTimeout(() => blip(1318, 1318, 0.45, 'sine', 0.18), 120)
}
export function boing() { blip(220, 520, 0.25, 'sine', 0.16) }
export function thud() {
  if (!ctx) return
  const t = ctx.currentTime
  const len = Math.floor(ctx.sampleRate * 0.16)
  const buf = ctx.createBuffer(1, len, ctx.sampleRate)
  const d = buf.getChannelData(0)
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len)
  const src = ctx.createBufferSource(); src.buffer = buf
  const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 280
  const g = ctx.createGain(); g.gain.value = 0.5
  src.connect(f); f.connect(g); g.connect(master)
  src.start(t)
}
