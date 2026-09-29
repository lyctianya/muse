<template>
  <a-textarea v-model="input" :rows="6" placeholder="输入要计算哈希的文本" @input="calc" />
  <a-descriptions :column="1" bordered style="margin-top: 12px">
    <a-descriptions-item v-for="h in hashes" :key="h.name" :label="h.name">
      <a-typography-text copyable code>{{ h.value || '—' }}</a-typography-text>
    </a-descriptions-item>
  </a-descriptions>
</template>
<script setup>
import { ref } from 'vue'
const input = ref('')
const hashes = ref([
  { name: 'MD5', value: '' }, { name: 'SHA-1', value: '' },
  { name: 'SHA-256', value: '' }, { name: 'SHA-512', value: '' },
])
async function digest(algo, text) {
  const buf = await crypto.subtle.digest(algo, new TextEncoder().encode(text))
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('')
}
// MD5（RFC1321 精简实现）
function md5(str) {
  const bytes = new TextEncoder().encode(str)
  const bitLen = bytes.length * 8
  const withPad = [...bytes, 0x80]
  while (withPad.length % 64 !== 56) withPad.push(0)
  const dv = new DataView(new ArrayBuffer(8))
  dv.setUint32(0, bitLen >>> 0, true); dv.setUint32(4, Math.floor(bitLen / 2 ** 32), true)
  withPad.push(...new Uint8Array(dv.buffer))
  let [a0, b0, c0, d0] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]
  const S = [7,12,17,22, 7,12,17,22, 7,12,17,22, 7,12,17,22, 5,9,14,20, 5,9,14,20, 5,9,14,20, 5,9,14,20, 4,11,16,23, 4,11,16,23, 4,11,16,23, 4,11,16,23, 6,10,15,21, 6,10,15,21, 6,10,15,21, 6,10,15,21]
  const K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32))
  const rol = (x, n) => (x << n) | (x >>> (32 - n))
  for (let off = 0; off < withPad.length; off += 64) {
    const M = []
    for (let i = 0; i < 16; i++) M.push(withPad[off + i * 4] | (withPad[off + i * 4 + 1] << 8) | (withPad[off + i * 4 + 2] << 16) | (withPad[off + i * 4 + 3] << 24))
    let [A, B, C, D] = [a0, b0, c0, d0]
    for (let i = 0; i < 64; i++) {
      let F, g
      if (i < 16) { F = (B & C) | (~B & D); g = i }
      else if (i < 32) { F = (D & B) | (~D & C); g = (5 * i + 1) % 16 }
      else if (i < 48) { F = B ^ C ^ D; g = (3 * i + 5) % 16 }
      else { F = C ^ (B | ~D); g = (7 * i) % 16 }
      F = (F + A + K[i] + M[g]) >>> 0
      A = D; D = C; C = B
      B = (B + rol(F, S[i])) >>> 0
    }
    a0 = (a0 + A) >>> 0; b0 = (b0 + B) >>> 0; c0 = (c0 + C) >>> 0; d0 = (d0 + D) >>> 0
  }
  const le = (x) => [x & 255, (x >> 8) & 255, (x >> 16) & 255, (x >> 24) & 255].map((b) => b.toString(16).padStart(2, '0')).join('')
  return le(a0) + le(b0) + le(c0) + le(d0)
}
let timer = null
function calc() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    const t = input.value
    if (!t) { hashes.value.forEach((h) => (h.value = '')); return }
    const [s1, s256, s512] = await Promise.all([
      digest('SHA-1', t), digest('SHA-256', t), digest('SHA-512', t),
    ])
    hashes.value[0].value = md5(t)
    hashes.value[1].value = s1
    hashes.value[2].value = s256
    hashes.value[3].value = s512
  }, 300)
}
</script>
