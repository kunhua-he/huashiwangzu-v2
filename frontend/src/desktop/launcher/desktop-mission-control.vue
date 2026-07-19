<template>
  <div
    v-if="show"
    class="mission-control glass-panel"
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
    <div v-else class="mc-grid">
      <button
        v-for="card in cards"
        :key="card.id"
        type="button"
        class="mc-card"
        :class="{ active: card.isActive, minimized: card.minimized }"
        @click="activate(card.id)"
      >
        <div class="mc-thumb" :style="thumbStyle(card)">
          <AppIcon :icon="card.icon" :app-key="card.appKey" :size="36" />
          <span class="mc-thumb-title">{{ card.title }}</span>
        </div>
        <div class="mc-meta">
          <span class="mc-title">{{ card.title }}</span>
          <span v-if="card.minimized" class="mc-badge">已最小化</span>
        </div>
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
    .sort((a, b) => b.zIndex - a.zIndex),
)

function thumbStyle(card: WindowState) {
  const 低 = 低内存策略().调度中心用占位卡
  if (低) {
    return {
      background: 'linear-gradient(160deg, rgba(248,250,252,.92), rgba(226,232,240,.88))',
    }
  }
  // 用几何比例画占位景深，避免昂贵截图
  const ratio = Math.max(0.4, Math.min(1.8, card.width / Math.max(1, card.height)))
  return {
    aspectRatio: String(ratio),
    background: card.isActive
      ? 'linear-gradient(165deg, rgba(255,255,255,.92), rgba(226,232,240,.78))'
      : 'linear-gradient(165deg, rgba(248,250,252,.86), rgba(203,213,225,.72))',
  }
}

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
  display: flex;
  flex-direction: column;
  padding: 28px 32px 40px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(28px) saturate(160%);
  -webkit-backdrop-filter: blur(28px) saturate(160%);
  color: rgba(248, 250, 252, 0.96);
}
.mc-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 22px;
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
  margin: auto;
  opacity: 0.8;
}
.mc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 18px;
  align-content: start;
  overflow: auto;
  padding-bottom: 24px;
}
.mc-card {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.mc-thumb {
  min-height: 140px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  gap: 10px;
  box-shadow: 0 18px 48px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.45);
  border: 1px solid rgba(255,255,255,.22);
  transition: transform 160ms var(--desktop-ease-spring), box-shadow 160ms ease;
}
.mc-card:hover .mc-thumb,
.mc-card.active .mc-thumb {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 24px 56px rgba(0,0,0,.34), 0 0 0 2px rgba(10,132,255,.55);
}
.mc-thumb-title {
  font: 600 13px/1.2 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  color: rgba(30, 41, 59, 0.9);
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 0 4px;
}
.mc-title {
  font: 500 12px/1.2 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  opacity: 0.92;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-badge {
  margin-left: auto;
  font-size: 10px;
  opacity: 0.7;
}
.mc-card.minimized .mc-thumb { opacity: 0.72; filter: grayscale(0.15); }
html.desktop-low-memory .mission-control {
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  background: rgba(15, 23, 42, 0.88);
}
</style>
