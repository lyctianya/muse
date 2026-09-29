/* 星尘收集：3D 接金币小游戏。
 * 玩家操控青色方块左右移动，接住金色星星得分，碰到红色炸弹扣命。
 * 动态 import('three')，不污染主包。
 */
export async function createGame(container, hooks = {}) {
  const THREE = await import('three')

  const W = container.clientWidth || 800
  const H = Math.min(560, window.innerHeight - 220)
  const BOUND = 7 // 左右边界

  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(W, H)
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0b1026)
  scene.fog = new THREE.Fog(0x0b1026, 18, 40)

  const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 100)
  camera.position.set(0, 7, 13)
  camera.lookAt(0, 2, 0)

  scene.add(new THREE.AmbientLight(0x8899ff, 0.7))
  const dir = new THREE.DirectionalLight(0xffffff, 1.2)
  dir.position.set(5, 12, 8)
  scene.add(dir)
  const point = new THREE.PointLight(0xd3a24a, 1.5, 30)
  point.position.set(0, 6, 4)
  scene.add(point)

  // 地面网格
  const grid = new THREE.GridHelper(30, 30, 0xd3a24a, 0x2a3358)
  grid.position.y = 0
  scene.add(grid)
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(30, 30),
    new THREE.MeshStandardMaterial({ color: 0x141b36, roughness: 0.9 })
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.02
  scene.add(ground)

  // 玩家
  const player = new THREE.Mesh(
    new THREE.BoxGeometry(1.6, 1.6, 1.6),
    new THREE.MeshStandardMaterial({ color: 0x22d3ee, emissive: 0x0e7490, roughness: 0.3 })
  )
  player.position.set(0, 0.8, 0)
  scene.add(player)
  const halo = new THREE.Mesh(
    new THREE.RingGeometry(1.1, 1.5, 32),
    new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.5, side: THREE.DoubleSide })
  )
  halo.rotation.x = -Math.PI / 2
  halo.position.y = 0.03
  scene.add(halo)

  const starGeo = new THREE.IcosahedronGeometry(0.55, 0)
  const starMat = new THREE.MeshStandardMaterial({ color: 0xffd166, emissive: 0xb45309, roughness: 0.3 })
  const bombGeo = new THREE.SphereGeometry(0.55, 16, 16)
  const bombMat = new THREE.MeshStandardMaterial({ color: 0xef4444, emissive: 0x7f1d1d, roughness: 0.4 })

  let items = [] // {mesh, kind: 'star'|'bomb', vy}
  let score = 0, lives = 3, running = false, over = false
  let speed = 1, elapsed = 0, spawnT = 0
  let moveDir = 0 // -1 左，1 右
  let raf = 0, last = 0

  const keys = {}
  function onKey(e, down) {
    keys[e.key] = down
    if (['ArrowLeft', 'ArrowRight', 'a', 'd', 'A', 'D'].includes(e.key)) e.preventDefault()
  }
  const kd = (e) => onKey(e, true)
  const ku = (e) => onKey(e, false)
  window.addEventListener('keydown', kd)
  window.addEventListener('keyup', ku)

  // 触摸/鼠标拖拽
  let dragX = null
  const onDown = (e) => { dragX = e.touches ? e.touches[0].clientX : e.clientX }
  const onMove = (e) => {
    if (dragX === null) return
    const x = e.touches ? e.touches[0].clientX : e.clientX
    const dx = x - dragX
    dragX = x
    player.position.x = Math.max(-BOUND, Math.min(BOUND, player.position.x + dx * 0.03))
  }
  const onUp = () => { dragX = null }
  renderer.domElement.addEventListener('pointerdown', onDown)
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)

  function spawn() {
    const isBomb = Math.random() < Math.min(0.32, 0.15 + elapsed * 0.004)
    const mesh = new THREE.Mesh(isBomb ? bombGeo : starGeo,
      isBomb ? bombMat : starMat)
    mesh.position.set((Math.random() * 2 - 1) * BOUND, 11, (Math.random() * 2 - 1) * 3)
    scene.add(mesh)
    items.push({ mesh, kind: isBomb ? 'bomb' : 'star', vy: (4 + Math.random() * 3) * speed, spin: Math.random() * 3 })
  }

  function update(dt) {
    elapsed += dt
    speed = 1 + elapsed / 45 // 难度递增
    // 键盘移动
    moveDir = 0
    if (keys.ArrowLeft || keys.a || keys.A) moveDir -= 1
    if (keys.ArrowRight || keys.d || keys.D) moveDir += 1
    player.position.x = Math.max(-BOUND, Math.min(BOUND, player.position.x + moveDir * 11 * dt))
    halo.position.x = player.position.x
    player.rotation.y += dt * 0.8

    spawnT -= dt
    if (spawnT <= 0) { spawn(); spawnT = Math.max(0.25, 0.9 - elapsed * 0.008) }

    for (let i = items.length - 1; i >= 0; i--) {
      const it = items[i]
      it.mesh.position.y -= it.vy * dt
      it.mesh.rotation.y += it.spin * dt
      it.mesh.rotation.x += it.spin * 0.6 * dt
      const dx = it.mesh.position.x - player.position.x
      const dz = it.mesh.position.z - player.position.z
      // 接到判定
      if (it.mesh.position.y < 1.9 && it.mesh.position.y > 0.2 && Math.abs(dx) < 1.3 && Math.abs(dz) < 1.6) {
        scene.remove(it.mesh)
        items.splice(i, 1)
        if (it.kind === 'star') {
          score += 10
          hooks.onScore && hooks.onScore(score)
        } else {
          lives -= 1
          hooks.onLives && hooks.onLives(lives)
          // 受击闪烁
          player.material.emissive.setHex(0xef4444)
          setTimeout(() => player.material.emissive.setHex(0x0e7490), 180)
          if (lives <= 0) { gameOver(); return }
        }
        continue
      }
      // 落地消失
      if (it.mesh.position.y < 0) {
        scene.remove(it.mesh)
        items.splice(i, 1)
      }
    }
  }

  function loop(t) {
    if (!running) return
    const dt = Math.min(0.05, (t - last) / 1000 || 0.016)
    last = t
    if (!over) update(dt)
    renderer.render(scene, camera)
    raf = requestAnimationFrame(loop)
  }

  function gameOver() {
    over = true
    running = false
    cancelAnimationFrame(raf)
    hooks.onGameOver && hooks.onGameOver(score)
  }

  return {
    start() {
      if (running) return
      running = true; over = false
      score = 0; lives = 3; elapsed = 0; speed = 1
      items.forEach((it) => scene.remove(it.mesh))
      items = []
      player.position.x = 0
      hooks.onScore && hooks.onScore(0)
      hooks.onLives && hooks.onLives(3)
      last = performance.now()
      raf = requestAnimationFrame(loop)
    },
    destroy() {
      running = false
      cancelAnimationFrame(raf)
      window.removeEventListener('keydown', kd)
      window.removeEventListener('keyup', ku)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      renderer.dispose()
      if (renderer.domElement.parentNode === container) container.removeChild(renderer.domElement)
    },
  }
}

export const GAME_ID = 'starfall'
export const GAME_NAME = '星尘收集'
