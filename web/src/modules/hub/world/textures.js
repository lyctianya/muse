/* 程序化 canvas 纹理：给方块建筑穿上"手工感" */
let THREE = null
async function three() {
  if (!THREE) THREE = await import('three')
  return THREE
}

function makeTex(cv, rx = 1, ry = 1) {
  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  tex.repeat.set(rx, ry)
  tex.anisotropy = 4
  return tex
}

function canvas(w, h) {
  const cv = document.createElement('canvas')
  cv.width = w; cv.height = h
  return [cv, cv.getContext('2d')]
}

/* 办公楼立面：窗格（部分亮灯） */
export async function facadeTexture(base = '#f5f5f0', litRatio = 0.25) {
  await three()
  const [cv, ctx] = canvas(256, 256)
  ctx.fillStyle = base
  ctx.fillRect(0, 0, 256, 256)
  const cols = 4, rows = 6
  const ww = 256 / cols, wh = 256 / rows
  for (let i = 0; i < cols; i++) {
    for (let j = 0; j < rows; j++) {
      const lit = Math.random() < litRatio
      ctx.fillStyle = lit ? '#ffe9a8' : '#5a6b7d'
      ctx.fillRect(i * ww + 8, j * wh + 8, ww - 16, wh - 16)
      ctx.fillStyle = 'rgba(255,255,255,0.35)'
      ctx.fillRect(i * ww + 8, j * wh + 8, ww - 16, 6)
    }
  }
  return makeTex(cv)
}

/* 柏油路：深灰 + 噪点 + 中央虚线 */
export async function roadTexture() {
  await three()
  const [cv, ctx] = canvas(128, 256)
  ctx.fillStyle = '#7d838d'
  ctx.fillRect(0, 0, 128, 256)
  // 噪点
  for (let i = 0; i < 500; i++) {
    ctx.fillStyle = `rgba(${Math.random() > 0.5 ? '255,255,255' : '0,0,0'},0.05)`
    ctx.fillRect(Math.random() * 128, Math.random() * 256, 2, 2)
  }
  // 中央虚线
  ctx.fillStyle = '#f5f5f0'
  for (let y = 0; y < 256; y += 64) ctx.fillRect(60, y + 8, 8, 36)
  // 边缘线
  ctx.fillStyle = 'rgba(245,245,240,0.7)'
  ctx.fillRect(6, 0, 4, 256)
  ctx.fillRect(118, 0, 4, 256)
  return makeTex(cv, 1, 4)
}

/* 洞洞板 */
export async function pegboardTexture() {
  await three()
  const [cv, ctx] = canvas(128, 128)
  ctx.fillStyle = '#d9a066'
  ctx.fillRect(0, 0, 128, 128)
  ctx.fillStyle = '#8a5a3b'
  for (let x = 16; x < 128; x += 24)
    for (let y = 16; y < 128; y += 24) {
      ctx.beginPath(); ctx.arc(x, y, 4, 0, 7); ctx.fill()
    }
  return makeTex(cv, 3, 2)
}

/* 横线纸 */
export async function paperTexture() {
  await three()
  const [cv, ctx] = canvas(128, 128)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, 128, 128)
  ctx.strokeStyle = '#bcd3e8'
  ctx.lineWidth = 2
  for (let y = 20; y < 128; y += 18) {
    ctx.beginPath(); ctx.moveTo(10, y); ctx.lineTo(118, y); ctx.stroke()
  }
  ctx.fillStyle = '#e5484d'
  ctx.fillRect(24, 0, 3, 128)
  return makeTex(cv)
}

/* 黑黄警示条纹 */
export async function hazardTexture() {
  await three()
  const [cv, ctx] = canvas(128, 32)
  ctx.fillStyle = '#f4d35e'
  ctx.fillRect(0, 0, 128, 32)
  ctx.fillStyle = '#2b2f36'
  for (let x = -32; x < 128; x += 32) {
    ctx.beginPath()
    ctx.moveTo(x, 32); ctx.lineTo(x + 16, 0); ctx.lineTo(x + 32, 0); ctx.lineTo(x + 16, 32)
    ctx.fill()
  }
  return makeTex(cv, 6, 1)
}

/* 木质指示牌文字 */
export async function signTexture(text) {
  await three()
  const [cv, ctx] = canvas(256, 96)
  ctx.fillStyle = '#8a5a3b'
  ctx.fillRect(0, 0, 256, 96)
  ctx.strokeStyle = '#5e3d26'
  ctx.lineWidth = 8
  ctx.strokeRect(4, 4, 248, 88)
  ctx.fillStyle = '#fff8e8'
  ctx.font = '700 44px "PingFang SC","Microsoft YaHei",sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, 128, 52)
  // 箭头
  ctx.beginPath()
  ctx.moveTo(216, 34); ctx.lineTo(238, 48); ctx.lineTo(216, 62); ctx.lineTo(216, 54); ctx.lineTo(196, 54); ctx.lineTo(196, 42); ctx.lineTo(216, 42)
  ctx.fill()
  return makeTex(cv)
}

/* 报纸亭菜单板 */
export async function menuTexture() {
  await three()
  const [cv, ctx] = canvas(128, 96)
  ctx.fillStyle = '#2b2f36'
  ctx.fillRect(0, 0, 128, 96)
  ctx.fillStyle = '#f4d35e'
  ctx.font = '700 20px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('MENU', 64, 24)
  ctx.fillStyle = '#e0e1dd'
  for (let i = 0; i < 4; i++) ctx.fillRect(16, 38 + i * 14, 96 - i * 12, 5)
  return makeTex(cv)
}

/* 尘土粒子贴图 */
export async function puffTexture() {
  await three()
  const [cv, ctx] = canvas(64, 64)
  const g = ctx.createRadialGradient(32, 32, 4, 32, 32, 30)
  g.addColorStop(0, 'rgba(255,255,255,0.9)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 64, 64)
  return makeTex(cv)
}

/* 喇叭气泡 "叭！" */
export async function honkTexture() {
  await three()
  const [cv, ctx] = canvas(128, 96)
  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.roundRect(8, 8, 112, 60, 18)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(40, 66); ctx.lineTo(30, 90); ctx.lineTo(58, 66)
  ctx.fill()
  ctx.fillStyle = '#e5484d'
  ctx.font = '700 38px "PingFang SC","Microsoft YaHei",sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('叭！', 64, 52)
  return makeTex(cv)
}
