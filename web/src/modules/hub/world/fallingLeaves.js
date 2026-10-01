/* 落叶：原站 Leaves 的 WebGL 实现
   - 从树冠位置持续飘落树叶粒子
   - 树叶旋转、摇摆、落地消失 */
import * as THREE from 'three'

export function createFallingLeaves(scene, treePositions, opts = {}) {
  const count = opts.count || 150
  const geo = new THREE.PlaneGeometry(0.25, 0.25)
  const mat = new THREE.MeshBasicMaterial({
    color: 0xd8cf3b, side: THREE.DoubleSide, transparent: true, opacity: 0.9,
  })
  const inst = new THREE.InstancedMesh(geo, mat, count)
  inst.frustumCulled = false
  scene.add(inst)

  const leaves = []
  const m4 = new THREE.Matrix4()
  const q = new THREE.Quaternion()
  const e = new THREE.Euler()
  const v = new THREE.Vector3()
  const s = new THREE.Vector3(1, 1, 1)

  // 初始化
  for (let i = 0; i < count; i++) {
    leaves.push(spawnLeaf(true))
  }

  function spawnLeaf(anywhere = false) {
    // 随机选一棵树
    const tp = treePositions[Math.floor(Math.random() * treePositions.length)]
    if (!tp) return { pos: new THREE.Vector3(), vel: new THREE.Vector3(), rot: 0, rotV: 0, sway: 0, life: 0 }
    return {
      pos: new THREE.Vector3(
        tp.x + (Math.random() - 0.5) * 3,
        anywhere ? Math.random() * 8 + 1 : tp.y + 4 + Math.random() * 2,
        tp.z + (Math.random() - 0.5) * 3
      ),
      vel: new THREE.Vector3((Math.random() - 0.5) * 0.5, -0.8 - Math.random() * 0.7, (Math.random() - 0.5) * 0.5),
      rot: Math.random() * Math.PI * 2,
      rotV: (Math.random() - 0.5) * 4,
      sway: Math.random() * Math.PI * 2,
      life: 1,
    }
  }

  function update(dt, windX = 0.3) {
    for (let i = 0; i < count; i++) {
      const l = leaves[i]
      // 下落 + 风 + 摇摆
      l.pos.y += l.vel.y * dt
      l.pos.x += (l.vel.x + windX + Math.sin(l.sway) * 0.5) * dt
      l.pos.z += l.vel.z * dt
      l.rot += l.rotV * dt
      l.sway += dt * 2

      // 落地或飞太远则重生
      if (l.pos.y < 0.1 || Math.abs(l.pos.x) > 95 || Math.abs(l.pos.z) > 95) {
        leaves[i] = spawnLeaf()
        continue
      }

      // 更新矩阵
      e.set(l.rot, l.sway * 0.5, 0)
      q.setFromEuler(e)
      v.copy(l.pos)
      m4.compose(v, q, s)
      inst.setMatrixAt(i, m4)
    }
    inst.instanceMatrix.needsUpdate = true
  }

  return { update, mesh: inst }
}
