<template>
  <nav
    ref="dockRef"
    class="desktop-taskbar mac-dock glass-dock"
    aria-label="Dock"
    @pointerleave="onDockLeave"
    @pointermove="onDockMove"
  >
    <div class="mac-dock-item-wrap" :style="itemStyle(0)">
      <button
        class="mac-dock-icon-button taskbar-start"
        type="button"
        title="Launchpad"
        aria-label="打开 Launchpad"
        :aria-pressed="launcherOpen"
        :style="iconStyle(0)"
        @click="emit('openLauncher')"
      >
        <AppIcon icon="Grid" app-key="launchpad" :size="48" />
      </button>
    </div>

    <div class="mac-dock-separator" aria-hidden="true" />

    <template v-for="(app, index) in dockApps" :key="app.appKey">
      <div
        v-if="app.isUtility && index > 0 && !dockApps[index - 1]?.isUtility"
        class="mac-dock-separator"
        aria-hidden="true"
      />
      <div
        class="mac-dock-item-wrap"
        :style="itemStyle(index + 1)"
        draggable="true"
        @dragstart="onDragStart(app.appKey, $event)"
        @dragover.prevent
        @drop.prevent="onDrop(app.appKey)"
      >
        <button
          class="mac-dock-icon-button mac-dock-app"
          type="button"
          :title="app.appName"
          :aria-label="app.appName"
          :data-dock-app-key="app.appKey"
          :aria-pressed="app.isActive"
          :class="{ 'is-bouncing': bounceKey === app.appKey, 'is-pinned': app.pinned }"
          :style="iconStyle(index + 1)"
          @click="activateApp(app)"
          @contextmenu.prevent="openAppMenu(app.appKey)"
        >
          <AppIcon :icon="app.icon" :app-key="app.appKey" :size="48" />
          <span v-if="app.isRunning" class="mac-dock-running-dot" />
          <span v-if="getProgress(app.appKey)" class="mac-dock-progress"><span :style="progressStyle(app.appKey)" /></span>
        </button>
        <div v-if="contextAppKey === app.appKey" class="mac-dock-menu glass-menu" role="menu">
          <strong>{{ app.appName }}</strong>
          <button v-for="windowItem in app.windows" :key="windowItem.id" type="button" role="menuitem" @click="emit('switchWindow', windowItem.id); closeAppMenu()">
            <Check v-if="windowItem.isActive" :size="13" /><span v-else class="mac-dock-menu-space" />{{ windowItem.title }}
          </button>
          <div v-if="app.windows.length" class="mac-dock-menu-separator" />
          <button type="button" role="menuitem" @click="emit('openApp', app.appKey); closeAppMenu()"><Plus :size="13" />{{ app.windows.length ? '新建窗口' : '打开' }}</button>
          <button type="button" role="menuitem" @click="togglePin(app); closeAppMenu()">
            <Pin :size="13" />{{ app.pinned ? '从 Dock 移除' : '在 Dock 中保留' }}
          </button>
          <button v-if="app.windows.length" type="button" role="menuitem" @click="hideAppWindows(app); closeAppMenu()"><Minus :size="13" />隐藏</button>
          <button v-if="app.windows.length" type="button" role="menuitem" class="is-danger" @click="quitAppWindows(app); closeAppMenu()"><X :size="13" />退出</button>
        </div>
      </div>
    </template>

    <div class="mac-dock-separator" aria-hidden="true" />

    <div class="mac-dock-item-wrap" :style="itemStyle(dockApps.length + 1)">
      <button
        class="mac-dock-icon-button"
        type="button"
        title="调度中心"
        aria-label="打开调度中心"
        :style="iconStyle(dockApps.length + 1)"
        @click="emit('openMissionControl')"
      >
        <AppIcon icon="Layers" app-key="mission-control" :size="48" />
      </button>
    </div>
    <div class="mac-dock-item-wrap" :style="itemStyle(dockApps.length + 2)">
      <button
        class="mac-dock-icon-button"
        type="button"
        title="Spotlight"
        aria-label="打开 Spotlight"
        :style="iconStyle(dockApps.length + 2)"
        @click="emit('openSpotlight')"
      >
        <AppIcon icon="Search" app-key="spotlight" :size="48" />
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Check, Minus, Pin, Plus, X } from 'lucide-vue-next'
import type { AppRegistryEntry, TaskbarItem } from '@/desktop/window-manager/window-types'
import AppIcon from '@/desktop/components/app-icon.vue'
import { activeProgress } from '@/desktop/feedback/desktop-feedback'
import { desktopConfig } from '@/desktop/config/desktop-preferences'

/** 基础边长 */
const BASE = 48
/** 最大放大倍数（系统 Dock 大约 1.5–1.7） */
const MAX_SCALE = 1.58
/** 影响半径（px，相对 dock 内容区） */
const RANGE = 96
const GAP = 10
const PAD_X = 12
const SEP_W = 13 // 1px 线 + 两侧 margin 约略

const props = withDefaults(defineProps<{ items: TaskbarItem[]; launcherOpen?: boolean; appList?: AppRegistryEntry[] }>(), {
  launcherOpen: false,
  appList: () => [],
})
const emit = defineEmits<{
  switchWindow: [id: string]
  openLauncher: []
  openSpotlight: []
  openMissionControl: []
  openApp: [appKey: string]
  closeWindow: [id: string]
}>()

const dockRef = ref<HTMLElement | null>(null)
/** 鼠标相对 dock 内容左缘的 X；null = 未悬停 */
const mouseRelX = ref<number | null>(null)
const contextAppKey = ref('')
const bounceKey = ref('')
const dragKey = ref('')
let bounceTimer: ReturnType<typeof setTimeout> | null = null

const dockApps = computed(() => {
  const canonicalByKey = new Map(props.appList.map(app => [app.appKey, app.canonicalAppKey || app.appKey]))
  const registered = new Map<string, AppRegistryEntry>()
  for (const app of props.appList.filter(app => app.windowType !== 'background-service')) {
    const canonicalKey = app.canonicalAppKey || app.appKey
    if (!registered.has(canonicalKey) || app.appKey === canonicalKey) registered.set(canonicalKey, app)
  }
  const utilityKeys = new Set(['recycle'])
  const pinned = (desktopConfig.dockPinned?.length
    ? desktopConfig.dockPinned
    : [...registered.entries()].filter(([, app]) => app.showOnDesktop).map(([key]) => key)
  ).map(k => canonicalByKey.get(k) || k)

  const runningKeys = props.items
    .map(item => item.appKey ? (canonicalByKey.get(item.appKey) || item.appKey) : '')
    .filter(Boolean) as string[]

  const orderPref = (desktopConfig.dockOrder || []).map(k => canonicalByKey.get(k) || k)
  const base = [...new Set([...orderPref, ...pinned, ...runningKeys])]
    .filter(key => registered.has(key) || runningKeys.includes(key))

  const main = base.filter(key => !utilityKeys.has(key))
  const utils = base.filter(key => utilityKeys.has(key))
  const order = [...main, ...utils]

  return order.map(appKey => {
    const app = registered.get(appKey)
    const windows = props.items
      .filter(item => item.appKey && (canonicalByKey.get(item.appKey) || item.appKey) === appKey)
      .sort((a, b) => Number(b.isActive) - Number(a.isActive))
    return {
      appKey,
      appName: app?.appName || windows[0]?.title || appKey,
      icon: app?.icon || windows[0]?.icon || 'Grid',
      windows,
      isRunning: windows.length > 0,
      isActive: windows.some(item => item.isActive),
      isUtility: utilityKeys.has(appKey),
      pinned: pinned.includes(appKey),
    }
  })
})

/**
 * 槽位序列（含分隔线占位），用于稳定的「未放大」中心坐标。
 * kind: icon | sep
 */
const layoutSlots = computed(() => {
  const slots: Array<{ kind: 'icon' | 'sep'; iconIndex?: number }> = []
  let iconIndex = 0
  // Launchpad
  slots.push({ kind: 'icon', iconIndex: iconIndex++ })
  slots.push({ kind: 'sep' })
  // apps
  dockApps.value.forEach((app, i) => {
    if (app.isUtility && i > 0 && !dockApps.value[i - 1]?.isUtility) {
      slots.push({ kind: 'sep' })
    }
    slots.push({ kind: 'icon', iconIndex: iconIndex++ })
  })
  slots.push({ kind: 'sep' })
  // mission + spotlight
  slots.push({ kind: 'icon', iconIndex: iconIndex++ })
  slots.push({ kind: 'icon', iconIndex: iconIndex++ })
  return slots
})

const iconCount = computed(() => dockApps.value.length + 3)

/**
 * 用「未放大」布局算每个图标中心（相对 dock 内容左缘，含 padding）。
 * 放大时真实宽度会变，但距离永远在未放大坐标系里算 → 不抖动。
 */
const baseLayout = computed(() => {
  const centers: number[] = Array(iconCount.value).fill(0)
  let x = PAD_X
  for (const slot of layoutSlots.value) {
    if (slot.kind === 'sep') {
      x += SEP_W + GAP
      continue
    }
    const idx = slot.iconIndex ?? 0
    centers[idx] = x + BASE / 2
    x += BASE + GAP
  }
  // 内容总宽（含左右 padding）
  const width = x - GAP + PAD_X
  return { centers, width }
})

/**
 * 把实际像素坐标映射到未放大坐标系。
 * Dock 从中心变宽时，避免鼠标和「逻辑中心」错位。
 */
function logicalMouseX(): number | null {
  const mx = mouseRelX.value
  const el = dockRef.value
  if (mx == null || !el) return null
  const actual = el.clientWidth || baseLayout.value.width
  if (actual <= 0) return mx
  return mx * (baseLayout.value.width / actual)
}

function scaleOf(index: number): number {
  const mx = logicalMouseX()
  if (mx == null) return 1
  const center = baseLayout.value.centers[index]
  if (center == null) return 1
  const distance = Math.abs(mx - center)
  if (distance >= RANGE) return 1
  const t = distance / RANGE
  return 1 + (MAX_SCALE - 1) * Math.cos((t * Math.PI) / 2)
}

function sizeOf(index: number): number {
  return Math.round(BASE * scaleOf(index))
}

/** 槽位宽度 = 图标真实宽度 → 邻居被挤开，边界不粘连 */
function itemStyle(index: number) {
  const size = sizeOf(index)
  return {
    width: `${size}px`,
    height: `${BASE}px`,
  }
}

/** 真实改宽高（不用 transform:scale 溢出叠边），再 translateY 抬起 */
function iconStyle(index: number) {
  const size = sizeOf(index)
  const lift = Math.max(0, size - BASE)
  return {
    width: `${size}px`,
    height: `${size}px`,
    transform: `translateY(-${lift}px)`,
    zIndex: size,
  }
}

function onDockMove(event: PointerEvent) {
  const el = dockRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  mouseRelX.value = event.clientX - rect.left
}
function onDockLeave() {
  mouseRelX.value = null
}

function bounce(appKey: string) {
  bounceKey.value = appKey
  if (bounceTimer) clearTimeout(bounceTimer)
  bounceTimer = setTimeout(() => { bounceKey.value = '' }, 700)
}
function activateApp(app: (typeof dockApps.value)[number]) {
  if (!app.windows.length) bounce(app.appKey)
  if (app.windows.length) emit('switchWindow', app.windows[0].id)
  else emit('openApp', app.appKey)
}
function getProgress(appKey: string) { return activeProgress.value.get(appKey) || null }
function progressStyle(appKey: string) {
  const entry = getProgress(appKey)
  if (!entry) return {}
  return { width: entry.progress === -1 ? '42%' : `${Math.min(100, entry.progress * 100)}%`, background: entry.color || '#0a84ff' }
}
function openAppMenu(appKey: string) { contextAppKey.value = appKey }
function closeAppMenu() { contextAppKey.value = '' }
function hideAppWindows(app: (typeof dockApps.value)[number]) {
  window.dispatchEvent(new CustomEvent('desktop:hide-app', { detail: { appKey: app.appKey } }))
}
function quitAppWindows(app: (typeof dockApps.value)[number]) {
  for (const w of app.windows) emit('closeWindow', w.id)
}
function togglePin(app: (typeof dockApps.value)[number]) {
  const pinned = new Set(desktopConfig.dockPinned || [])
  if (pinned.has(app.appKey)) pinned.delete(app.appKey)
  else pinned.add(app.appKey)
  desktopConfig.dockPinned = [...pinned]
  const order = [...(desktopConfig.dockOrder || [])]
  if (!order.includes(app.appKey)) order.push(app.appKey)
  desktopConfig.dockOrder = order
}
function onDragStart(appKey: string, event: DragEvent) {
  dragKey.value = appKey
  event.dataTransfer?.setData('text/plain', appKey)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
function onDrop(targetKey: string) {
  const from = dragKey.value
  dragKey.value = ''
  if (!from || from === targetKey) return
  const keys = dockApps.value.map(a => a.appKey)
  const fromIdx = keys.indexOf(from)
  const toIdx = keys.indexOf(targetKey)
  if (fromIdx < 0 || toIdx < 0) return
  keys.splice(fromIdx, 1)
  keys.splice(toIdx, 0, from)
  desktopConfig.dockOrder = keys
  const pinned = new Set(desktopConfig.dockPinned || [])
  for (const k of keys) pinned.add(k)
  desktopConfig.dockPinned = [...pinned]
}
function onPointerDown(event: PointerEvent) {
  if (!(event.target as HTMLElement | null)?.closest('.mac-dock-item-wrap')) closeAppMenu()
}
onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onUnmounted(() => {
  document.removeEventListener('pointerdown', onPointerDown)
  if (bounceTimer) clearTimeout(bounceTimer)
})
</script>

<style scoped>
.mac-dock {
  position: absolute;
  left: 50%;
  bottom: var(--desktop-dock-bottom-gap);
  z-index: var(--z-dock);
  min-height: var(--desktop-dock-height);
  max-width: calc(100% - 24px);
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 6px 12px 8px;
  transform: translateX(-50%);
  user-select: none;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.06) 42%, rgba(0, 0, 0, 0.08)),
    var(--glass-dock-bg, rgba(255, 255, 255, 0.22));
}

/* 槽宽 = 图标视觉宽：放大时把邻居挤开，不会叠边 */
.mac-dock-item-wrap {
  position: relative;
  flex: 0 0 auto;
  display: grid;
  place-items: end center;
  height: 48px;
  transition: width 70ms linear;
  will-change: width;
}

.mac-dock-icon-button {
  position: relative;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: rgba(255, 255, 255, 0.94);
  display: grid;
  place-items: center;
  cursor: default;
  /* 真实改宽高，禁止 transform:scale 画出槽外 */
  transition:
    width 70ms linear,
    height 70ms linear,
    transform 70ms linear;
  will-change: width, height, transform;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.2));
}
.mac-dock-icon-button :deep(.app-icon) {
  width: 100% !important;
  height: 100% !important;
}
.mac-dock-icon-button:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.9);
  outline-offset: 3px;
  border-radius: 12px;
}

.mac-dock-icon-button.is-bouncing {
  animation: dock-bounce 700ms var(--desktop-ease-spring);
}
@keyframes dock-bounce {
  0% { translate: 0 0; }
  18% { translate: 0 -16px; }
  36% { translate: 0 0; }
  54% { translate: 0 -10px; }
  72% { translate: 0 0; }
  86% { translate: 0 -4px; }
  100% { translate: 0 0; }
}

.taskbar-start {
  background: transparent;
  box-shadow: none;
}

.mac-dock-separator {
  width: 1px;
  height: 36px;
  margin: 0 1px 4px;
  align-self: flex-end;
  background: rgba(255, 255, 255, 0.28);
  flex: 0 0 auto;
}

.mac-dock-running-dot {
  position: absolute;
  left: 50%;
  bottom: -6px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.55);
  box-shadow: 0 0 0 0.5px rgba(255, 255, 255, 0.28);
  pointer-events: none;
}
.mac-dock-progress {
  position: absolute;
  left: 14%;
  right: 14%;
  bottom: 3px;
  height: 2px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.22);
  overflow: hidden;
}
.mac-dock-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.mac-dock-menu {
  position: absolute;
  left: 50%;
  bottom: 72px;
  width: 220px;
  padding: 6px;
  transform: translateX(-50%);
  color: var(--desktop-ink);
  z-index: var(--z-system-popover);
  border-radius: 10px;
}
.mac-dock-menu strong {
  display: block;
  padding: 6px 8px 4px;
  font: var(--desktop-font-caption);
  color: var(--desktop-ink-muted);
}
.mac-dock-menu button {
  width: 100%;
  height: 26px;
  padding: 0 8px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  display: grid;
  grid-template-columns: 14px 1fr;
  align-items: center;
  gap: 7px;
  text-align: left;
  font: 400 13px/1 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
}
.mac-dock-menu button:hover { background: var(--desktop-selection); color: white; }
.mac-dock-menu button.is-danger:hover { background: #ff3b30; }
.mac-dock-menu-space { width: 13px; }
.mac-dock-menu-separator { height: 0.5px; margin: 5px 8px; background: rgba(60, 60, 67, 0.18); }

html.desktop-micro-off .mac-dock-icon-button,
html.desktop-micro-off .mac-dock-item-wrap {
  transition: none !important;
}
@media (prefers-reduced-motion: reduce) {
  .mac-dock-icon-button,
  .mac-dock-item-wrap {
    transition: none !important;
  }
}
@media (max-width: 760px) {
  .mac-dock {
    max-width: calc(100% - 12px);
    overflow-x: auto;
    overflow-y: hidden;
  }
}
</style>
