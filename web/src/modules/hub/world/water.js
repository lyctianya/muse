/* 水面：原站 Water 的 WebGL 实现
   - 动画法线扰动 + 菲涅尔反射
   - 半透明蓝色 */
import * as THREE from 'three'

export function createWater(scene, opts = {}) {
  const size = opts.size || 40
  const geo = new THREE.PlaneGeometry(size, size, 32, 32)
  geo.rotateX(-Math.PI / 2)
  
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    uniforms: {
      uTime: { value: 0 },
      uColorDeep: { value: new THREE.Color(0x1a5f9e) },
      uColorShallow: { value: new THREE.Color(0x4aa8d8) },
      uSunDir: { value: new THREE.Vector3(0.5, 1, 0.3).normalize() },
    },
    vertexShader: `
      uniform float uTime;
      varying vec3 vPos;
      varying vec3 vNormal;
      void main() {
        vPos = position;
        vec3 p = position;
        // 波浪
        p.y += sin(p.x * 0.5 + uTime * 1.2) * 0.08;
        p.y += cos(p.z * 0.4 + uTime * 0.9) * 0.08;
        vNormal = normal;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform vec3 uColorDeep;
      uniform vec3 uColorShallow;
      uniform vec3 uSunDir;
      varying vec3 vPos;
      varying vec3 vNormal;
      void main() {
        // 法线扰动
        vec3 n = normalize(vNormal + vec3(
          sin(vPos.x * 2.0 + uTime * 2.0) * 0.1,
          0.0,
          cos(vPos.z * 2.0 + uTime * 1.5) * 0.1
        ));
        // 菲涅尔
        vec3 viewDir = normalize(cameraPosition - vPos);
        float fres = pow(1.0 - max(dot(n, viewDir), 0.0), 2.0);
        vec3 col = mix(uColorDeep, uColorShallow, fres * 0.7 + 0.2);
        // 太阳高光
        vec3 h = normalize(uSunDir + viewDir);
        float spec = pow(max(dot(n, h), 0.0), 64.0);
        col += vec3(1.0, 0.95, 0.8) * spec * 0.8;
        gl_FragColor = vec4(col, 0.85);
      }
    `,
  })
  
  const mesh = new THREE.Mesh(geo, mat)
  mesh.position.set(opts.x || 0, opts.y || 0.1, opts.z || 0)
  scene.add(mesh)
  
  return {
    mesh,
    update(t) {
      mat.uniforms.uTime.value = t
    },
  }
}
