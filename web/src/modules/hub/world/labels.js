/* 悬浮中文标签：canvas 纹理 sprite */
export async function makeLabel(text, accent = '#d3a24a') {
  const THREE = await import('three')
  const W = 512, H = 128
  const cv = document.createElement('canvas')
  cv.width = W; cv.height = H
  const ctx = cv.getContext('2d')
  // 圆角白底
  const r = 36
  ctx.fillStyle = 'rgba(255,255,255,0.96)'
  ctx.beginPath()
  ctx.roundRect(8, 8, W - 16, H - 16, r)
  ctx.fill()
  ctx.lineWidth = 6
  ctx.strokeStyle = accent
  ctx.beginPath()
  ctx.roundRect(8, 8, W - 16, H - 16, r)
  ctx.stroke()
  // 文字（Pally 为原站字体，未加载完则回退系统字体）
  ctx.fillStyle = '#1a2340'
  ctx.font = '700 56px Pally, "PingFang SC", "Microsoft YaHei", sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, W / 2, H / 2 + 2)
  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 4
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false })
  const sp = new THREE.Sprite(mat)
  sp.scale.set(5.2, 1.3, 1)
  return sp
}
