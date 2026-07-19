<template>
  <nav class="desktop-taskbar mac-dock glass-dock" aria-label="Dock" @mouseleave="hoveredIndex = -1">
    <div class="mac-dock-item-wrap" :class="magnifyClass(0)" @mouseenter="hoveredIndex = 0">
      <button class="taskbar-start mac-dock-icon-button" type="button" title="Launchpad" aria-label="打开 Launchpad" :aria-pressed="launcherOpen" @click="emit('openLauncher')">
        <Grid3X3 :size="27" :stroke-width="1.7" />
      </button>
    </div>
    <div class="mac-dock-separator" />
    <template v-for="(app, index) in dockApps" :key="app.appKey">
      <div v-if="app.isUtility && index > 0 && !dockApps[index - 1]?.isUtility" class="mac-dock-separator" />
      <div
        class="mac-dock-item-wrap"
        :class="magnifyClass(index + 1)"
        draggable="true"
        @mouseenter="hoveredIndex = index + 1"
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
          @click="activateApp(app)"
          @contextmenu.prevent="openAppMenu(app.appKey)"
        >
          <AppIcon :icon="app.icon" :app-key="app.appKey" :size="46" />
          <span v-if="app.isRunning" class="mac-dock-running-dot" />
          <span v-if="getProgress(app.appKey)" class="mac-dock-progress"><span :style="progressStyle(app.appKey)" /></span>
        </button>
        <div v-if="contextAppKey === app.appKey" class="mac-dock-menu glass-menu" role="menu">
          <strong>{{ app.appName }}</strong>
          <button v-for="windowItem in app.windows" :key="windowItem.id" type="button" role="menuitem" @click="emit('switchWindow', windowItem.id); closeAppMenu()"><Check v-if="windowItem.isActive" :size="13" /><span v-else class="mac-dock-menu-space" />{{ windowItem.title }}</button>
          <div v-if="app.windows.length" class="mac-dock-menu-separator" />
          <button type="button" role="menuitem" @click="emit('openApp', app.appKey); closeAppMenu()"><Plus :size="13" />{{ app.windows.length ? '新建窗口' : '打开' }}</button>
          <button
            type="button"
            role="menuitem"
            @click="togglePin(app); closeAppMenu()"
          >
            <Pin :size="13" />{{ app.pinned ? '从 Dock 移除' : '在 Dock 中保留' }}
          </button>
          <button
            v-if="app.windows.length"
            type="button"
            role="menuitem"
            @click="hideAppWindows(app); closeAppMenu()"
          ><Minus :size="13" />隐藏</button>
          <button
            v-if="app.windows.length"
            type="button"
            role="menuitem"
            class="is-danger"
            @click="quitAppWindows(app); closeAppMenu()"
          ><X :size="13" />退出</button>
        </div>
      </div>
    </template>
    <div class="mac-dock-separator" />
    <div class="mac-dock-item-wrap" :class="magnifyClass(dockApps.length + 1)" @mouseenter="hoveredIndex = dockApps.length + 1">
      <button class="mac-dock-icon-button" type="button" title="调度中心" aria-label="打开调度中心" @click="emit('openMissionControl')"><Layers :size="26" :stroke-width="1.8" /></button>
    </div>
    <div class="mac-dock-item-wrap" :class="magnifyClass(dockApps.length + 2)" @mouseenter="hoveredIndex = dockApps.length + 2">
      <button class="mac-dock-icon-button" type="button" title="Spotlight" aria-label="打开 Spotlight" @click="emit('openSpotlight')"><Search :size="28" :stroke-width="1.8" /></button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Check, Grid3X3, Layers, Minus, Pin, Plus, Search, X } from 'lucide-vue-next'
import type { AppRegistryEntry, TaskbarItem } from '@/desktop/window-manager/window-types'
import AppIcon from '@/desktop/components/app-icon.vue'
import { activeProgress } from '@/desktop/feedback/desktop-feedback'
import { desktopConfig } from '@/desktop/config/desktop-preferences'

const props = withDefaults(defineProps<{ items: TaskbarItem[]; launcherOpen?: boolean; appList?: AppRegistryEntry[] }>(), { launcherOpen: false, appList: () => [] })
const emit = defineEmits<{
  switchWindow: [id: string]
  openLauncher: []
  openSpotlight: []
  openMissionControl: []
  openApp: [appKey: string]
  closeWindow: [id: string]
}>()
const hoveredIndex = ref(-1)
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
function magnifyClass(index: number) {
  const hover = hoveredIndex.value
  if (hover < 0) return {}
  const distance = Math.abs(index - hover)
  if (distance === 0) return { 'is-hovered': true }
  if (distance === 1) return { 'is-neighbor': true }
  if (distance === 2) return { 'is-near': true }
  return {}
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
  // 保证 order 里有该 key
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
  // 拖过的都视为固定
  const pinned = new Set(desktopConfig.dockPinned || [])
  for (const k of keys) pinned.add(k)
  desktopConfig.dockPinned = [...pinned]
}
function onPointerDown(event: PointerEvent) {
  if (!(event.target as HTMLElement | null)?.closest('.mac-dock-item-wrap')) closeAppMenu()
}
onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onUnmounted(() => document.removeEventListener('pointerdown', onPointerDown))
</script>

<style scoped>
.mac-dock{position:absolute;left:50%;bottom:var(--desktop-dock-bottom-gap);z-index:var(--z-dock);height:var(--desktop-dock-height);max-width:calc(100% - 24px);display:flex;align-items:flex-end;gap:4px;padding:var(--desktop-dock-padding);transform:translateX(-50%);user-select:none}
.mac-dock-item-wrap{position:relative;width:48px;height:48px;display:grid;place-items:end center;flex:0 0 48px;transition:width var(--desktop-duration-fast) var(--desktop-ease-spring),margin var(--desktop-duration-fast) var(--desktop-ease-spring)}
.mac-dock-item-wrap.is-hovered{width:62px}
.mac-dock-item-wrap.is-neighbor{width:54px}
.mac-dock-item-wrap.is-near{width:50px}
.mac-dock-icon-button{position:relative;width:48px;height:48px;padding:0;border:0;border-radius:12px;background:transparent;color:rgba(255,255,255,.92);display:grid;place-items:center;transform-origin:50% 100%;transition:transform var(--desktop-duration-fast) var(--desktop-ease-spring),filter var(--desktop-duration-fast) var(--desktop-ease-spring)}
.mac-dock-icon-button:hover{filter:brightness(1.06)}
.mac-dock-icon-button:focus-visible{outline:2px solid rgba(255,255,255,.94);outline-offset:3px}
.mac-dock-item-wrap.is-hovered .mac-dock-icon-button{transform:translateY(-14px) scale(1.32)}
.mac-dock-item-wrap.is-neighbor .mac-dock-icon-button{transform:translateY(-8px) scale(1.16)}
.mac-dock-item-wrap.is-near .mac-dock-icon-button{transform:translateY(-4px) scale(1.07)}
.mac-dock-icon-button.is-bouncing{animation:dock-bounce 700ms var(--desktop-ease-spring)}
@keyframes dock-bounce{
  0%{transform:translateY(0) scale(1)}
  18%{transform:translateY(-16px) scale(1.08)}
  36%{transform:translateY(0) scale(1)}
  54%{transform:translateY(-10px) scale(1.05)}
  72%{transform:translateY(0) scale(1)}
  86%{transform:translateY(-4px) scale(1.02)}
  100%{transform:translateY(0) scale(1)}
}
.taskbar-start{background:linear-gradient(145deg,rgba(37,99,235,.92),rgba(14,165,233,.92));box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 4px 12px rgba(0,0,0,.18)}
.mac-dock-separator{width:1px;height:36px;margin:0 3px 5px;background:rgba(255,255,255,.28)}
.mac-dock-running-dot{position:absolute;left:50%;bottom:-5px;width:4px;height:4px;border-radius:50%;transform:translateX(-50%);background:rgba(255,255,255,.9);box-shadow:0 1px 2px rgba(0,0,0,.5)}
.mac-dock-progress{position:absolute;left:5px;right:5px;bottom:1px;height:3px;border-radius:4px;background:rgba(0,0,0,.24);overflow:hidden}
.mac-dock-progress span{display:block;height:100%;border-radius:inherit}
.mac-dock-menu{position:absolute;left:50%;bottom:62px;width:230px;padding:5px;transform:translateX(-50%);color:var(--desktop-ink);z-index:var(--z-system-popover)}
.mac-dock-menu strong{display:block;padding:7px 8px 5px;font:var(--desktop-font-caption);color:var(--desktop-ink-muted)}
.mac-dock-menu button{width:100%;height:28px;padding:0 8px;border:0;border-radius:6px;background:transparent;color:inherit;display:grid;grid-template-columns:14px 1fr;align-items:center;gap:7px;text-align:left;font:var(--desktop-font-menu)}
.mac-dock-menu button:hover{background:var(--desktop-selection);color:white}
.mac-dock-menu-space{width:13px}
.mac-dock-menu-separator{height:1px;margin:4px 7px;background:var(--desktop-divider)}
html.desktop-micro-off .mac-dock-icon-button,html.desktop-micro-off .mac-dock-item-wrap{transition:none!important}
@media(prefers-reduced-motion:reduce){.mac-dock-icon-button,.mac-dock-item-wrap{transition:none!important}.mac-dock-item-wrap.is-hovered .mac-dock-icon-button,.mac-dock-item-wrap.is-neighbor .mac-dock-icon-button,.mac-dock-item-wrap.is-near .mac-dock-icon-button{transform:none}.mac-dock-item-wrap.is-hovered,.mac-dock-item-wrap.is-neighbor,.mac-dock-item-wrap.is-near{width:48px}}
@media(max-width:760px){.mac-dock{max-width:calc(100% - 12px);overflow-x:auto;overflow-y:hidden}.mac-dock-item-wrap.is-hovered .mac-dock-icon-button,.mac-dock-item-wrap.is-neighbor .mac-dock-icon-button,.mac-dock-item-wrap.is-near .mac-dock-icon-button{transform:none}.mac-dock-item-wrap.is-hovered,.mac-dock-item-wrap.is-neighbor,.mac-dock-item-wrap.is-near{width:48px}}
</style>
