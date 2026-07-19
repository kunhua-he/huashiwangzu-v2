<template>
  <div
    v-if="show"
    class="mission-control"
    role="dialog"
    aria-label="调度中心"
    @keydown.escape.prevent="emit('close')"
    @mousedown.self="emit('close')"
  >
    <header class="mc-header">
      <strong>调度中心</strong>
      <span class="mc-hint">点击窗口切换 · Esc 关闭</span>
      <button type="button" class="mc-close" aria-label="关闭调度中心" @click="emit('close')">×</button>
    </header>
    <div v-if="!cards.length" class="mc-empty">没有打开的窗口</div>
    <div v-else class="mc-stage" :style="stageStyle">
      <button
        v-for="card in layoutCards"
        :key="card.id"
        type="button"
        class="mc-card"
        :class="{ active: card.isActive, minimized: card.minimized }"
        :style="card.style"
        @click="activate(card.id)"
      >
        <div class="mc-chrome">
          <span class="mc-dot close" />
          <span class="mc-dot min" />
          <span class="mc-dot max" />
          <span class="mc-chrome-title">{{ card.title }}</span>
        </div>
        <div class="mc-body">
          <AppIcon :icon="card.icon" :app-key="card.appKey" :size="card.iconSize" />
          <div class="mc-body-meta">
            <strong>{{ card.title }}</strong>
            <small>{{ card.appKey }} · {{ Math.round(card.width) }}×{{ Math.round(card.height) }}</small>
          </div>
        </div>
        <span v-if="card.minimized" class="mc-badge">已最小化</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import type { WindowState } from '@/desktop/window-manager/window-types'
import AppIcon from '@/desktop/components/app-icon.vue'
import { 低内存策略 } from '@/desktop/runtime'

const props = defineProps<{
  show: boolean
  windows: WindowState[]
}>()
const emit = defineEmits<{ close: []; activate: [id: string] }>()

const cards = computed(() =>
  [...props.windows]
    .filter(w => w.windowType !== 'background-service')
    .sort((a, b) => a.zIndex - b.zIndex),
)

const stageStyle = computed(() => ({
  // 预留 header
}))

type LayoutCard = WindowState & {
  style: Record<string, string>
  iconSize: number
}

const layoutCards = computed<LayoutCard[]>(() => {
  const list = cards.value
  if (!list.length) return []
  const 低 = 低内存策略().调度中心用占位卡
  const vw = typeof window !== 'undefined' ? window.innerWidth : 1280
  const vh = typeof window !== 'undefined' ? window.innerHeight : 800
  const padX = 48
  const padTop = 88
  const padBottom = 48
  const stageW = Math.max(320, vw - padX * 2)
  const stageH = Math.max(240, vh - padTop - padBottom)

  // 真实几何归一化到 stage（保留相对位置/尺寸）
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const w of list) {
    const x = w.minimized ? w.x + 40 : w.x
    const y = w.minimized ? w.y + 40 : w.y
    const width = Math.max(200, w.width)
    const height = Math.max(140, w.height)
    minX = Math.min(minX, x)
    minY = Math.min(minY, y)
    maxX = Math.max(maxX, x + width)
    maxY = Math.max(maxY, y + height)
  }
  const worldW = Math.max(1, maxX - minX)
  const worldH = Math.max(1, maxY - minY)
  const scale = Math.min(stageW / worldW, stageH / worldH, 低 ? 0.42 : 0.55) * 0.92

  // 居中
  const contentW = worldW * scale
  const contentH = worldH * scale
  const offsetX = padX + (stageW - contentW) / 2
  const offsetY = padTop + (stageH - contentH) / 2

  return list.map((w) => {
    const width = Math.max(180, w.width) * scale
    const height = Math.max(120, w.height) * scale
    const x = offsetX + (w.x - minX) * scale
    const y = offsetY + (w.y - minY) * scale
    return {
      ...w,
      iconSize: Math.max(28, Math.min(56, Math.round(Math.min(width, height) * 0.22))),
      style: {
        left: `${x}px`,
        top: `${y}px`,
        width: `${width}px`,
        height: `${height}px`,
        zIndex: String(100 + w.zIndex),
        opacity: w.minimized ? '0.72' : '1',
      },
    }
  })
})

function activate(id: string) {
  emit('activate', id)
  emit('close')
}

function onKey(e: KeyboardEvent) {
  if (!props.show) return
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKey, true))
onUnmounted(() => window.removeEventListener('keydown', onKey, true))
</script>

<style scoped>
.mission-control {
  position: absolute;
  inset: 0;
  z-index: var(--z-mission-control, 14500);
  background: rgba(8, 12, 22, 0.52);
  backdrop-filter: blur(30px) saturate(160%);
  -webkit-backdrop-filter: blur(30px) saturate(160%);
  color: rgba(248, 250, 252, 0.96);
}
.mc-header {
  position: absolute;
  left: 32px;
  right: 32px;
  top: 22px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 2;
}
.mc-header strong {
  font: 600 18px/1.2 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
}
.mc-hint {
  opacity: 0.72;
  font: 400 12px/1.2 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
}
.mc-close {
  margin-left: auto;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 999px;
  background: rgba(255,255,255,.12);
  color: inherit;
  font-size: 18px;
  cursor: pointer;
}
.mc-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  opacity: 0.8;
}
.mc-stage {
  position: absolute;
  inset: 0;
}
.mc-card {
  position: absolute;
  border: 0;
  padding: 0;
  border-radius: 12px;
  overflow: hidden;
  color: inherit;
  text-align: left;
  cursor: pointer;
  background: linear-gradient(180deg, rgba(252,252,253,.96), rgba(236,236,240,.92));
  box-shadow: 0 18px 48px rgba(0,0,0,.32), 0 0 0 .5px rgba(255,255,255,.28);
  transition: transform 160ms var(--desktop-ease-spring), box-shadow 160ms ease;
  display: flex;
  flex-direction: column;
}
.mc-card:hover,
.mc-card.active {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 26px 60px rgba(0,0,0,.38), 0 0 0 2px rgba(10,132,255,.6);
}
.mc-chrome {
  height: 28px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  background: linear-gradient(180deg, rgba(244,244,246,.95), rgba(230,230,234,.9));
  border-bottom: .5px solid rgba(60,60,67,.12);
  color: rgba(30,41,59,.88);
}
.mc-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  box-shadow: inset 0 0 0 .5px rgba(0,0,0,.12);
}
.mc-dot.close { background: #ff5f57; }
.mc-dot.min { background: #febc2e; }
.mc-dot.max { background: #28c840; }
.mc-chrome-title {
  margin-left: 6px;
  min-width: 0;
  flex: 1;
  font: 600 11px/1 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-body {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 12px;
  color: rgba(30, 41, 59, 0.9);
}
.mc-body-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mc-body-meta strong {
  font: 600 13px/1.2 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}
.mc-body-meta small {
  font: 400 11px/1.2 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  opacity: 0.65;
}
.mc-badge {
  position: absolute;
  right: 8px;
  bottom: 8px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(15,23,42,.55);
  color: white;
}
.mc-card.minimized {
  filter: grayscale(0.12);
}
html.desktop-low-memory .mission-control {
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  background: rgba(15, 23, 42, 0.9);
}
@media (prefers-reduced-motion: reduce) {
  .mc-card { transition: none; }
}
</style>
