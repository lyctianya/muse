import * as THREE from 'three/webgpu'
import { color } from 'three/tsl'
import { Game } from '../../Game.js'
import { MeshDefaultMaterial } from '../../Materials/MeshDefaultMaterial.js'

/**
 * Stylized Pixiu (貔貅) statue on a stone pedestal — Muse module entrance landmark.
 */
export class PixiuStatue
{
  constructor(anchorPosition)
  {
    this.game = Game.getInstance()
    this.group = new THREE.Group()
    this.group.name = 'pixiuStatue'
    this.group.position.set(anchorPosition.x, 0, anchorPosition.z)
    // Face toward approach (lower Z)
    this.group.rotation.y = Math.PI

    this.materials = this.createMaterials()
    this.buildPedestal()
    this.buildPixiu()
    this.buildColliders(anchorPosition)

    this.game.scene.add(this.group)
  }

  createMaterials()
  {
    const solid = (hex, extras = {}) => new MeshDefaultMaterial({
      colorNode: color(hex),
      hasWater: false,
      ...extras,
    })

    return {
      gold: solid('#d4a017'),
      goldDark: solid('#8a6810'),
      goldBright: solid('#f0d060'),
      jade: solid('#2f6b4f'),
      stone: solid('#5a534c'),
      stoneDark: solid('#3d3833'),
      eye: solid('#1a1208'),
    }
  }

  mesh(geometry, material, position = [0, 0, 0], rotation = [0, 0, 0], scale = [1, 1, 1])
  {
    const m = new THREE.Mesh(geometry, material)
    m.position.set(...position)
    m.rotation.set(...rotation)
    m.scale.set(...scale)
    m.castShadow = true
    m.receiveShadow = true
    return m
  }

  buildPedestal()
  {
    const base = this.mesh(
      new THREE.CylinderGeometry(1.35, 1.5, 0.35, 12),
      this.materials.stoneDark,
      [0, 0.175, 0],
    )
    const mid = this.mesh(
      new THREE.CylinderGeometry(1.1, 1.2, 0.55, 12),
      this.materials.stone,
      [0, 0.62, 0],
    )
    const top = this.mesh(
      new THREE.CylinderGeometry(1.25, 1.15, 0.18, 12),
      this.materials.stoneDark,
      [0, 0.98, 0],
    )
    // Jade accent ring
    const ring = this.mesh(
      new THREE.TorusGeometry(1.05, 0.06, 8, 24),
      this.materials.jade,
      [0, 0.9, 0],
      [Math.PI / 2, 0, 0],
    )
    this.group.add(base, mid, top, ring)
    this.pedestalTop = 1.07
  }

  buildPixiu()
  {
    const pixiu = new THREE.Group()
    pixiu.name = 'pixiu'
    pixiu.position.y = this.pedestalTop
    // Sit facing forward (+Z local, toward player after group PI rot → -Z world)
    pixiu.rotation.y = 0

    const y0 = 0

    // Haunches / seated body
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.55, 16, 12),
      this.materials.gold,
      [0, y0 + 0.55, -0.15],
      [0, 0, 0],
      [1.05, 0.95, 1.25],
    ))

    // Chest
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.42, 14, 12),
      this.materials.goldBright,
      [0, y0 + 0.7, 0.35],
      [0.25, 0, 0],
      [1.05, 1.0, 1.1],
    ))

    // Neck
    pixiu.add(this.mesh(
      new THREE.CylinderGeometry(0.22, 0.28, 0.35, 10),
      this.materials.gold,
      [0, y0 + 1.05, 0.55],
      [0.55, 0, 0],
    ))

    // Head
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.38, 14, 12),
      this.materials.goldBright,
      [0, y0 + 1.28, 0.85],
      [0, 0, 0],
      [1.05, 0.95, 1.15],
    ))

    // Snout
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.18, 10, 8),
      this.materials.gold,
      [0, y0 + 1.18, 1.2],
      [0.3, 0, 0],
      [1.1, 0.8, 1.3],
    ))

    // Horns
    pixiu.add(this.mesh(
      new THREE.ConeGeometry(0.08, 0.35, 8),
      this.materials.goldDark,
      [-0.14, y0 + 1.62, 0.78],
      [0.35, 0, 0.25],
    ))
    pixiu.add(this.mesh(
      new THREE.ConeGeometry(0.08, 0.35, 8),
      this.materials.goldDark,
      [0.14, y0 + 1.62, 0.78],
      [0.35, 0, -0.25],
    ))

    // Ears
    pixiu.add(this.mesh(
      new THREE.ConeGeometry(0.1, 0.22, 6),
      this.materials.gold,
      [-0.32, y0 + 1.48, 0.7],
      [0, 0, 0.6],
    ))
    pixiu.add(this.mesh(
      new THREE.ConeGeometry(0.1, 0.22, 6),
      this.materials.gold,
      [0.32, y0 + 1.48, 0.7],
      [0, 0, -0.6],
    ))

    // Eyes
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.06, 8, 6),
      this.materials.eye,
      [-0.16, y0 + 1.35, 1.12],
    ))
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.06, 8, 6),
      this.materials.eye,
      [0.16, y0 + 1.35, 1.12],
    ))

    // Front paws
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.16, 10, 8),
      this.materials.goldDark,
      [-0.32, y0 + 0.22, 0.55],
      [0, 0, 0],
      [1, 0.7, 1.3],
    ))
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.16, 10, 8),
      this.materials.goldDark,
      [0.32, y0 + 0.22, 0.55],
      [0, 0, 0],
      [1, 0.7, 1.3],
    ))

    // Hind paws
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.18, 10, 8),
      this.materials.goldDark,
      [-0.35, y0 + 0.2, -0.45],
      [0, 0, 0],
      [1.1, 0.75, 1.2],
    ))
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.18, 10, 8),
      this.materials.goldDark,
      [0.35, y0 + 0.2, -0.45],
      [0, 0, 0],
      [1.1, 0.75, 1.2],
    ))

    // Wings
    const wingGeo = new THREE.SphereGeometry(0.55, 12, 8, 0, Math.PI)
    const wingL = this.mesh(wingGeo, this.materials.goldDark, [-0.55, y0 + 0.85, -0.05], [0.2, -0.4, 1.1], [0.35, 0.9, 0.7])
    const wingR = this.mesh(wingGeo, this.materials.goldDark, [0.55, y0 + 0.85, -0.05], [0.2, 0.4, -1.1], [0.35, 0.9, 0.7])
    pixiu.add(wingL, wingR)

    // Curled tail
    pixiu.add(this.mesh(
      new THREE.TorusGeometry(0.28, 0.08, 8, 16, Math.PI * 1.4),
      this.materials.gold,
      [0.15, y0 + 0.7, -0.7],
      [0.4, 0.8, 0.3],
    ))
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.1, 8, 6),
      this.materials.goldBright,
      [0.35, y0 + 0.95, -0.85],
    ))

    // Collar jewel
    pixiu.add(this.mesh(
      new THREE.SphereGeometry(0.1, 10, 8),
      this.materials.jade,
      [0, y0 + 0.95, 0.72],
    ))

    this.group.add(pixiu)
  }

  buildColliders(anchorPosition)
  {
    this.game.objects.add(
      null,
      {
        type: 'fixed',
        friction: 0.5,
        restitution: 0,
        colliders: [
          {
            shape: 'cuboid',
            parameters: [1.2, 0.55, 1.2],
            position: {
              x: anchorPosition.x,
              y: 0.55,
              z: anchorPosition.z,
            },
          },
          {
            shape: 'cuboid',
            parameters: [0.7, 0.85, 0.85],
            position: {
              x: anchorPosition.x,
              y: 1.9,
              z: anchorPosition.z,
            },
          },
        ],
      },
    )
  }
}
