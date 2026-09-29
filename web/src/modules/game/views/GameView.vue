<template>
  <a-card title="游戏">
    <a-row :gutter="16">
      <a-col :span="16">
        <a-card :bordered="false" style="background: #0b1026">
          <div style="display: flex; gap: 16px; align-items: center; margin-bottom: 12px; color: #fff">
            <a-tag size="large" color="gold">得分 {{ score }}</a-tag>
            <a-tag size="large" :color="lives > 1 ? 'green' : 'red'">生命 {{ '❤'.repeat(Math.max(0, lives)) }}</a-tag>
            <a-tag size="large">我的最佳 {{ best }}</a-tag>
            <a-button v-if="!playing" type="primary" @click="start">开始游戏</a-button>
            <span v-else style="color: #86909c; font-size: 12px">← → / A D 移动，或拖拽；接金星 +10，躲红球</span>
          </div>
          <div ref="stage" style="border-radius: 8px; overflow: hidden" />
          <a-result v-if="gameOver" status="info" title="游戏结束" :subtitle="`本局得分：${score}`" style="padding: 12px">
            <template #extra>
              <a-button type="primary" @click="start">再来一局</a-button>
            </template>
          </a-result>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="排行榜" :bordered="false">
          <a-list :data="board" :bordered="false">
            <template #empty><a-empty description="暂无成绩，来当第一个！" /></template>
            <a-list-item v-for="(r, i) in board" :key="i">
              <a-space>
                <a-tag :color="i === 0 ? 'gold' : i === 1 ? 'arcoblue' : i === 2 ? 'orange' : 'gray'">{{ i + 1 }}</a-tag>
                <span>{{ r.username || '匿名' }}</span>
              </a-space>
              <template #actions><b>{{ r.score }}</b></template>
            </a-list-item>
          </a-list>
        </a-card>
        <a-card title="游戏说明" :bordered="false" style="margin-top: 16px">
          <p style="font-size: 13px; color: #666; line-height: 1.8">
            <b>星尘收集</b>：操控青色方块接住从天而降的金色星星（+10 分），
            避开红色炸弹（碰到扣 1 命）。3 条命，速度随时间递增。
            成绩自动记入排行榜。
          </p>
        </a-card>
      </a-col>
    </a-row>
  </a-card>
</template>

<script setup>
import { getJSON, postJSON } from '../../../platform/utils/api.js'
import { createGame, GAME_ID } from '../games/starfall.js'
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Message } from '@arco-design/web-vue'

const stage = ref(null)
const score = ref(0)
const lives = ref(3)
const best = ref(0)
const board = ref([])
const playing = ref(false)
const gameOver = ref(false)
let game = null
let submitted = false

async function loadBoard() {
  try {
    const [b, m] = await Promise.all([
      getJSON(`/api/game/scores?game_id=${GAME_ID}`),
      getJSON(`/api/game/my-best?game_id=${GAME_ID}`),
    ])
    board.value = b.items || []
    best.value = m.best || 0
  } catch (e) { /* ignore */ }
}

async function start() {
  if (!game) {
    game = await createGame(stage.value, {
      onScore: (s) => { score.value = s },
      onLives: (l) => { lives.value = l },
      onGameOver: (s) => {
        playing.value = false
        gameOver.value = true
        submitScore(s)
      },
    })
  }
  submitted = false
  gameOver.value = false
  playing.value = true
  game.start()
}

async function submitScore(s) {
  if (submitted || s <= 0) return
  submitted = true
  try {
    await postJSON('/api/game/scores', { game_id: GAME_ID, score: s })
    Message.success('成绩已记入排行榜')
    loadBoard()
  } catch (e) {
    Message.error(`成绩提交失败：${e.message}`)
  }
}

onMounted(loadBoard)
onBeforeUnmount(() => { game && game.destroy() })
</script>
