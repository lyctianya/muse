import * as THREE from 'three/webgpu'
import { Game } from '../../Game.js'
import { InteractivePoints } from '../../InteractivePoints.js'
import { MUSE_PORTALS } from '../../../musePortals.js'

export { MUSE_PORTALS }

/** Muse business portals — placeholder buildings + InteractivePoints → vue-router bridge */
export class MusePortalsArea
{
  constructor()
  {
    this.game = Game.getInstance()
    this.group = new THREE.Group()
    this.group.name = 'musePortals'
    this.game.scene.add(this.group)

    this.portals = []
    for (const def of MUSE_PORTALS)
      this.createPortal(def)
  }

  createPortal(def)
  {
    const [x, y, z] = def.position
    const building = new THREE.Group()
    building.position.set(x, y, z)

    const body = new THREE.Mesh(
      new THREE.BoxGeometry(3.2, 4.2, 3.2),
      new THREE.MeshStandardNodeMaterial({ color: def.color }),
    )
    body.position.y = 2.1
    body.castShadow = true
    body.receiveShadow = true
    building.add(body)

    const roof = new THREE.Mesh(
      new THREE.BoxGeometry(3.6, 0.35, 3.6),
      new THREE.MeshStandardNodeMaterial({ color: '#1e293b' }),
    )
    roof.position.y = 4.4
    roof.castShadow = true
    building.add(roof)

    this.group.add(building)

    const pointPos = new THREE.Vector3(x, 0.05, z + 2.4)
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

    this.portals.push({ def, building, interactivePoint })
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
