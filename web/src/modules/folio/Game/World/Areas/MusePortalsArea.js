import * as THREE from 'three/webgpu'
import { color, texture } from 'three/tsl'
import { Game } from '../../Game.js'
import { InteractivePoints } from '../../InteractivePoints.js'
import { MeshDefaultMaterial } from '../../Materials/MeshDefaultMaterial.js'
import { MUSE_AVENUE, MUSE_PORTALS } from '../../../musePortals.js'

export { MUSE_PORTALS }

/**
 * Muse module entrances as a roadside avenue:
 * wooden signposts + themed miniature props + InteractivePoints.
 */
export class MusePortalsArea
{
  constructor()
  {
    this.game = Game.getInstance()
    this.group = new THREE.Group()
    this.group.name = 'musePortals'
    this.game.scene.add(this.group)

    this.portals = []
    this.materials = this.createMaterials()

    this.createPath()
    for (let i = 0; i < MUSE_PORTALS.length; i++)
      this.createPortal(MUSE_PORTALS[i], i)
  }

  createMaterials()
  {
    const solid = (hex, extras = {}) => new MeshDefaultMaterial({
      colorNode: color(hex),
      hasWater: false,
      ...extras,
    })

    return {
      post: solid('#6b4f35'),
      postCap: solid('#4a3422'),
      board: solid('#f4efe4'),
      boardEdge: solid('#d9d0bf'),
      path: solid('#b9a48a'),
      pathEdge: solid('#8f7a62'),
      metal: solid('#7d8794'),
      dark: solid('#2a2f36'),
      paper: solid('#f7f2e8'),
      accent: {},
    }
  }

  accentMaterial(hex)
  {
    if (!this.materials.accent[hex])
    {
      this.materials.accent[hex] = new MeshDefaultMaterial({
        colorNode: color(hex),
        hasWater: false,
      })
    }
    return this.materials.accent[hex]
  }

  mesh(geometry, material, position = [0, 0, 0], rotation = [0, 0, 0])
  {
    const m = new THREE.Mesh(geometry, material)
    m.position.set(...position)
    m.rotation.set(...rotation)
    m.castShadow = true
    m.receiveShadow = true
    return m
  }

  createPath()
  {
    const count = MUSE_PORTALS.length
    const length = (count - 1) * MUSE_AVENUE.spacing + 6
    const centerX = MUSE_AVENUE.origin[0] + ((count - 1) * MUSE_AVENUE.spacing) * 0.5
    const z = MUSE_AVENUE.origin[2]

    const bed = this.mesh(
      new THREE.BoxGeometry(length, 0.08, 3.2),
      this.materials.path,
      [centerX, 0.04, z],
    )
    this.group.add(bed)

    const curbA = this.mesh(
      new THREE.BoxGeometry(length, 0.16, 0.22),
      this.materials.pathEdge,
      [centerX, 0.08, z - 1.55],
    )
    const curbB = this.mesh(
      new THREE.BoxGeometry(length, 0.16, 0.22),
      this.materials.pathEdge,
      [centerX, 0.08, z + 1.55],
    )
    this.group.add(curbA, curbB)
  }

  createPortal(def, index)
  {
    const x = MUSE_AVENUE.origin[0] + index * MUSE_AVENUE.spacing
    const y = MUSE_AVENUE.origin[1]
    const z = MUSE_AVENUE.origin[2]
    const facing = MUSE_AVENUE.facing

    const station = new THREE.Group()
    station.name = `musePortal_${def.id}`
    station.position.set(x, y, z)
    station.rotation.y = facing

    // Signpost
    const post = this.mesh(
      new THREE.CylinderGeometry(0.12, 0.14, 3.1, 8),
      this.materials.post,
      [0, 1.55, 0],
    )
    const cap = this.mesh(
      new THREE.BoxGeometry(0.42, 0.12, 0.42),
      this.materials.postCap,
      [0, 3.15, 0],
    )
    const board = this.mesh(
      new THREE.BoxGeometry(2.2, 1.05, 0.12),
      this.materials.board,
      [0.95, 2.35, 0.05],
    )
    const boardFrame = this.mesh(
      new THREE.BoxGeometry(2.34, 1.18, 0.06),
      this.materials.boardEdge,
      [0.95, 2.35, 0],
    )

    const label = this.createSignLabel(def.title, def.accent)
    label.position.set(0.95, 2.35, 0.13)
    station.add(post, cap, boardFrame, board, label)

    // Themed prop beside the post
    const prop = this.createThemeProp(def)
    prop.position.set(1.7 * MUSE_AVENUE.propSide, 0, -1.15)
    station.add(prop)

    this.group.add(station)

    // Interactive point slightly in front of the sign face
    const forward = new THREE.Vector3(0, 0, 1.55).applyAxisAngle(new THREE.Vector3(0, 1, 0), facing)
    const pointPos = new THREE.Vector3(x, 0.05, z).add(forward)

    const interactivePoint = this.game.interactivePoints.create(
      pointPos,
      def.title,
      InteractivePoints.ALIGN_RIGHT,
      InteractivePoints.STATE_CONCEALED,
      () =>
      {
        this.game.inputs.interactiveButtons.clearItems()
        this.navigate(def)
      },
      () =>
      {
        this.game.inputs.interactiveButtons.addItems(['interact'])
      },
      () =>
      {
        this.game.inputs.interactiveButtons.removeItems(['interact'])
      },
      () =>
      {
        this.game.inputs.interactiveButtons.removeItems(['interact'])
      },
    )

    this.portals.push({ def, station, interactivePoint })
  }

  createSignLabel(title, accentHex)
  {
    const width = 512
    const height = 256
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')

    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = '#f4efe4'
    ctx.fillRect(0, 0, width, height)

    // Accent stripe
    ctx.fillStyle = accentHex
    ctx.fillRect(0, 0, 28, height)

    ctx.fillStyle = '#1f1a14'
    ctx.font = '700 92px "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(title, width * 0.52, height * 0.5)

    const map = new THREE.CanvasTexture(canvas)
    map.colorSpace = THREE.SRGBColorSpace
    map.minFilter = THREE.LinearFilter
    map.magFilter = THREE.LinearFilter
    map.generateMipmaps = false
    map.flipY = true
    map.needsUpdate = true

    const material = new MeshDefaultMaterial({
      colorNode: texture(map).rgb,
      hasWater: false,
    })
    material.map = map

    const plane = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 0.92), material)
    plane.castShadow = false
    plane.receiveShadow = false
    return plane
  }

  createThemeProp(def)
  {
    const group = new THREE.Group()
    const accent = this.accentMaterial(def.accent)

    switch (def.theme)
    {
      case 'stock':
        this.buildStock(group, accent)
        break
      case 'blog':
        this.buildBlog(group, accent)
        break
      case 'gallery':
        this.buildGallery(group, accent)
        break
      case 'game':
        this.buildGame(group, accent)
        break
      case 'news':
        this.buildNews(group, accent)
        break
      case 'tools':
        this.buildTools(group, accent)
        break
      case 'files':
        this.buildFiles(group, accent)
        break
      case 'sync':
        this.buildSync(group, accent)
        break
      case 'users':
        this.buildUsers(group, accent)
        break
      default:
        group.add(this.mesh(new THREE.BoxGeometry(1, 1, 1), accent, [0, 0.5, 0]))
    }

    return group
  }

  buildStock(group, accent)
  {
    // Ticker booth + chart slabs
    group.add(this.mesh(new THREE.BoxGeometry(1.6, 1.4, 1.1), this.materials.dark, [0, 0.7, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.35, 0.75, 0.08), accent, [0, 1.05, 0.58]))
    const bars = [0.35, 0.7, 0.45, 0.9, 0.55]
    bars.forEach((h, i) =>
    {
      group.add(this.mesh(
        new THREE.BoxGeometry(0.14, h, 0.08),
        this.materials.board,
        [-0.42 + i * 0.22, 0.72 + h * 0.5, 0.64],
      ))
    })
    group.add(this.mesh(new THREE.BoxGeometry(1.8, 0.12, 1.3), this.materials.postCap, [0, 1.46, 0]))
  }

  buildBlog(group, accent)
  {
    // Desk + typewriter + paper
    group.add(this.mesh(new THREE.BoxGeometry(1.7, 0.14, 1.0), this.materials.post, [0, 0.78, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(0.12, 0.78, 0.12), this.materials.post, [-0.7, 0.39, -0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.12, 0.78, 0.12), this.materials.post, [0.7, 0.39, -0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.12, 0.78, 0.12), this.materials.post, [-0.7, 0.39, 0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.12, 0.78, 0.12), this.materials.post, [0.7, 0.39, 0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.9, 0.35, 0.7), this.materials.metal, [0, 1.05, 0]))
    group.add(this.mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.55, 10), accent, [0, 1.2, 0], [0, 0, Math.PI * 0.5]))
    group.add(this.mesh(new THREE.BoxGeometry(0.45, 0.02, 0.55), this.materials.paper, [0.55, 0.93, 0.05], [0, 0.2, 0]))
  }

  buildGallery(group, accent)
  {
    // Easel + frame
    group.add(this.mesh(new THREE.BoxGeometry(0.1, 1.8, 0.1), this.materials.post, [-0.45, 0.9, -0.2], [0.15, 0, 0.12]))
    group.add(this.mesh(new THREE.BoxGeometry(0.1, 1.8, 0.1), this.materials.post, [0.45, 0.9, -0.2], [0.15, 0, -0.12]))
    group.add(this.mesh(new THREE.BoxGeometry(0.1, 1.5, 0.1), this.materials.post, [0, 0.75, 0.35], [-0.25, 0, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.3, 1.0, 0.08), this.materials.dark, [0, 1.25, 0], [0.12, 0, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.05, 0.75, 0.04), accent, [0, 1.25, 0.06], [0.12, 0, 0]))
  }

  buildGame(group, accent)
  {
    // Arcade cabinet
    group.add(this.mesh(new THREE.BoxGeometry(1.3, 2.0, 1.0), this.materials.dark, [0, 1.0, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.1, 0.7, 0.08), accent, [0, 1.45, 0.52]))
    group.add(this.mesh(new THREE.BoxGeometry(1.15, 0.35, 0.55), this.materials.metal, [0, 0.75, 0.35]))
    group.add(this.mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.25, 8), this.materials.board, [-0.25, 1.0, 0.5]))
    group.add(this.mesh(new THREE.SphereGeometry(0.1, 8, 8), accent, [-0.25, 1.15, 0.5]))
    group.add(this.mesh(new THREE.BoxGeometry(0.18, 0.08, 0.18), this.materials.board, [0.25, 0.95, 0.52]))
  }

  buildNews(group, accent)
  {
    // Newsstand + papers
    group.add(this.mesh(new THREE.BoxGeometry(1.5, 1.1, 0.7), this.materials.dark, [0, 0.55, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.6, 0.1, 0.8), this.materials.postCap, [0, 1.15, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.2, 0.7, 0.06), accent, [0, 1.6, -0.05]))
    group.add(this.mesh(new THREE.BoxGeometry(0.55, 0.02, 0.7), this.materials.paper, [-0.35, 1.22, 0.15], [0, 0.15, 0.08]))
    group.add(this.mesh(new THREE.BoxGeometry(0.55, 0.02, 0.7), this.materials.paper, [0.35, 1.22, 0.15], [0, -0.1, -0.06]))
    group.add(this.mesh(new THREE.BoxGeometry(0.35, 0.45, 0.08), this.materials.board, [0.7, 0.7, 0.35]))
  }

  buildTools(group, accent)
  {
    // Workbench + tools
    group.add(this.mesh(new THREE.BoxGeometry(1.9, 0.16, 1.0), this.materials.post, [0, 0.85, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(0.14, 0.85, 0.14), this.materials.post, [-0.8, 0.42, -0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.14, 0.85, 0.14), this.materials.post, [0.8, 0.42, -0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.14, 0.85, 0.14), this.materials.post, [-0.8, 0.42, 0.35]))
    group.add(this.mesh(new THREE.BoxGeometry(0.14, 0.85, 0.14), this.materials.post, [0.8, 0.42, 0.35]))
    group.add(this.mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.9, 8), this.materials.metal, [-0.35, 1.05, 0.1], [0, 0, 1.1]))
    group.add(this.mesh(new THREE.BoxGeometry(0.25, 0.12, 0.35), accent, [-0.05, 1.05, 0.15]))
    group.add(this.mesh(new THREE.CylinderGeometry(0.12, 0.16, 0.25, 8), this.materials.metal, [0.45, 1.05, 0]))
  }

  buildFiles(group, accent)
  {
    // Filing cabinet
    group.add(this.mesh(new THREE.BoxGeometry(1.2, 1.8, 0.9), this.materials.metal, [0, 0.9, 0]))
    for (let i = 0; i < 3; i++)
    {
      const yy = 0.4 + i * 0.5
      group.add(this.mesh(new THREE.BoxGeometry(1.05, 0.38, 0.08), this.materials.dark, [0, yy, 0.48]))
      group.add(this.mesh(new THREE.BoxGeometry(0.25, 0.06, 0.1), accent, [0, yy, 0.56]))
    }
    group.add(this.mesh(new THREE.BoxGeometry(0.7, 0.12, 0.5), this.materials.paper, [0.95, 0.2, 0.1], [0, 0.4, 0]))
  }

  buildSync(group, accent)
  {
    // Antenna / radar dish
    group.add(this.mesh(new THREE.CylinderGeometry(0.12, 0.18, 1.5, 8), this.materials.metal, [0, 0.75, 0]))
    group.add(this.mesh(new THREE.SphereGeometry(0.55, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.55), accent, [0, 1.7, 0], [0.6, 0.4, 0]))
    group.add(this.mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.7, 6), this.materials.dark, [0.15, 1.85, 0.2], [0.8, 0.2, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(0.8, 0.12, 0.8), this.materials.postCap, [0, 0.06, 0]))
  }

  buildUsers(group, accent)
  {
    // Reception desk + badge
    group.add(this.mesh(new THREE.BoxGeometry(1.8, 0.9, 0.8), this.materials.post, [0, 0.45, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(1.9, 0.12, 0.9), this.materials.board, [0, 0.96, 0]))
    group.add(this.mesh(new THREE.BoxGeometry(0.55, 0.7, 0.08), accent, [0, 1.45, -0.2]))
    group.add(this.mesh(new THREE.CircleGeometry(0.16, 12), this.materials.paper, [0, 1.55, -0.15]))
    group.add(this.mesh(new THREE.BoxGeometry(0.45, 0.28, 0.04), this.materials.dark, [0.55, 1.1, 0.4], [-0.3, 0.2, 0]))
  }

  navigate(def)
  {
    const bridge = this.game.museBridge
    if (!bridge || typeof bridge.navigate !== 'function')
    {
      this.game.notifications?.show(`无法打开「${def.title}」`, 'danger', 3)
      return
    }
    bridge.navigate(def)
  }
}
