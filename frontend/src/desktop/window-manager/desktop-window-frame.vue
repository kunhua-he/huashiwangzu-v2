<template>
  <div
    v-if="windowType !== 'background-service'"
    ref="rootEl"
    class="desktop-window glass-window"
    :class="[windowClasses, { 'desktop-window-finder': isFinderWindow }]"
    :style="windowStyle"
    :data-window-id="id"
    :data-accepts-drop="appKey === 'desktop' ? 'true' : undefined"
    role="dialog"
    :aria-label="title"
    @mousedown.capture="$emit('activate', id)"
  >
    <div
      class="window-titlebar"
      @mousedown="handleTitlebarMouseDown"
      @dblclick="$emit('maximize', id)"
    >
      <div class="window-title-info">
        <AppIcon :icon="icon" :app-key="appKey" :size="16" />
        <span class="window-title">{{ windowTitleText }}</span>
      </div>

      <div class="window-action-buttons">
        <button
          v-if="isFinderWindow"
          class="window-tab-add"
          type="button"
          title="新建标签"
          aria-label="新建标签"
          @click.stop="addFinderTab"
        >+</button>
        <button class="window-action-btn window-action-close" @click.stop="requestClose" title="关闭" aria-label="关闭" />
        <button v-if="windowType !== 'panel'" class="window-action-btn window-action-minimize" @click.stop="handleMinimize" title="最小化" aria-label="最小化" />
        <button v-if="windowType !== 'tool' && windowType !== 'background-service'" class="window-action-btn window-action-maximize" @click.stop="$emit('maximize', id)" title="缩放" aria-label="缩放" />
      </div>
    </div>
    <div
      v-if="isFinderWindow && finderTabs.length > 1"
      class="window-finder-tabs"
      role="tablist"
    >
      <button
        v-for="tab in finderTabs"
        :key="tab.id"
        type="button"
        class="window-finder-tab"
        :class="{ active: tab.id === activeFinderTabId }"
        role="tab"
        @click.stop="activateFinderTab(tab.id)"
      >
        <span class="window-finder-tab-label">{{ tab.title }}</span>
        <span
          class="window-finder-tab-close"
          title="关闭标签"
          @click.stop="closeFinderTab(tab.id)"
        >×</span>
      </button>
    </div>
    <div v-if="hasMountedContent" class="window-content" v-show="contentVisible">
      <div class="window-content-padding">
        <template v-if="currentComponent && !loadError">
          <Suspense>
            <component
              :is="currentComponent"
              :key="isFinderWindow ? activeFinderTabId : id"
              v-bind="finderComponentBind"
            />
            <template #fallback>
              <AsyncPaneState :title="`正在启动${title}`" />
            </template>
          </Suspense>
        </template>
        <AsyncPaneState v-else-if="loadError" :title="`${title}启动失败`" :error="loadError" @retry="retryLoad" />
        <AsyncPaneState v-else title="应用不可用" description="应用未找到或暂不支持此操作。" />
      </div>
    </div>
    <div v-for="direction in windowInteraction.resizeDirections" v-if="resizable && !maximized" :key="direction" :class="['resize-handle', `resize-handle-${direction}`]" @mousedown.stop="windowInteraction.startResize(direction, $event)" />
  </div>
  <div
    v-if="snapPreview"
    class="window-snap-preview"
    :class="`window-snap-preview-${snapPreview.kind}`"
    :style="snapPreviewStyle"
    aria-hidden="true"
  />
</template>
<script setup lang="ts">
import { computed, ref, defineAsyncComponent, onMounted, onUnmounted, watch } from 'vue'
import { getApp } from '@/desktop/app-registry/app-registry'
import { useWindowInteraction } from './use-window-interaction'
import { desktopConfig } from '@/desktop/config/desktop-preferences'
import {
  标记应用活跃,
  标记应用空闲,
  窗内容空闲毫秒,
  是否应冷启动内容,
} from '@/desktop/runtime'
import AppIcon from '@/desktop/components/app-icon.vue'
import AsyncPaneState from '@/shared/components/async-pane-state.vue'

type WindowGeometry = { x: number; y: number; width: number; height: number }

const props = defineProps<{
  id: string
  title: string
  icon: string
  x: number
  y: number
  width: number
  height: number
  zIndex: number
  minimized: boolean
  maximized: boolean
  isActive: boolean
  appKey: string
  payload?: Record<string, unknown>
  preMaximizeState?: WindowGeometry
  animationOrigin?: { x: number; y: number; width: number; height: number }
}>()

const emit = defineEmits<{
  (e: 'activate', id: string): void
  (e: 'close', id: string): void
  (e: 'minimize', id: string): void
  (e: 'maximize', id: string, restoreState?: WindowGeometry): void
  (e: 'update-position', id: string, x: number, y: number): void
  (e: 'update-geometry', id: string, x: number, y: number, w: number, h: number): void
}>()

const loadError = ref('')
const loadAttempt = ref(0)
const entered = ref(false)
const closing = ref(false)
const minimizing = ref(false)
const restoring = ref(false)
const openingFromOrigin = ref(false)
/** 最小化后真正卸载内容；会话恢复的最小化窗默认冷壳 */
const contentVisible = ref(是否应冷启动内容(props.minimized))
const hasMountedContent = ref(是否应冷启动内容(props.minimized))
let enterFrame = 0
let closeTimer: ReturnType<typeof window.setTimeout> | null = null
let minimizeTimer: ReturnType<typeof window.setTimeout> | null = null
let restoreTimer: ReturnType<typeof window.setTimeout> | null = null
let idleUnloadTimer: ReturnType<typeof window.setTimeout> | null = null
let appActiveCounted = false

const animDuration = computed(() => desktopConfig.windowAnimationDuration)

function 清除空闲卸载定时器() {
  if (idleUnloadTimer) {
    window.clearTimeout(idleUnloadTimer)
    idleUnloadTimer = null
  }
}

function 调度空闲卸载内容() {
  清除空闲卸载定时器()
  const ttl = Math.max(5_000, 窗内容空闲毫秒())
  idleUnloadTimer = window.setTimeout(() => {
    idleUnloadTimer = null
    if (!props.minimized || closing.value) return
    // 真正卸载 Vue 子树，释放实例内存；窗口壳与会话状态保留
    contentVisible.value = false
    hasMountedContent.value = false
  }, ttl)
}

function 确保内容已挂载() {
  清除空闲卸载定时器()
  contentVisible.value = true
  hasMountedContent.value = true
}

function 计入应用活跃() {
  if (appActiveCounted) return
  标记应用活跃(props.appKey)
  appActiveCounted = true
}

function 释放应用活跃() {
  if (!appActiveCounted) return
  标记应用空闲(props.appKey)
  appActiveCounted = false
}

watch(() => props.appKey, () => { loadError.value = '' })

// 最小化/还原动画 + 空闲卸载
watch(() => props.minimized, (minimized, oldMinimized) => {
  if (minimizeTimer) window.clearTimeout(minimizeTimer)
  if (restoreTimer) window.clearTimeout(restoreTimer)

  if (minimized && !oldMinimized) {
    // 正在最小化 → 播放最小化动画
    minimizing.value = true
    applyMinimizeTargetVars()
    minimizeTimer = window.setTimeout(() => {
      contentVisible.value = false
      minimizing.value = false
      调度空闲卸载内容()
    }, animDuration.value)
  } else if (!minimized && oldMinimized) {
    // 从最小化还原 → 重新挂载内容并播放还原动画
    确保内容已挂载()
    restoring.value = true
    applyMinimizeTargetVars()
    restoreTimer = window.setTimeout(() => {
      restoring.value = false
    }, animDuration.value)
  } else if (minimized) {
    contentVisible.value = false
    调度空闲卸载内容()
  } else {
    确保内容已挂载()
  }
}, { immediate: true })

watch(() => props.isActive, (active) => {
  if (active && !props.minimized) 确保内容已挂载()
})

function getTaskbarButtonRect(): { x: number; y: number } | null {
  const btn = document.querySelector(`[data-dock-app-key="${props.appKey}"]`) as HTMLElement | null
  if (btn) {
    const rect = btn.getBoundingClientRect()
    const parent = rootEl.value?.parentElement
    const parentRect = parent?.getBoundingClientRect()
    return {
      x: rect.left - (parentRect?.left ?? 0) + rect.width / 2,
      y: rect.top - (parentRect?.top ?? 0) + rect.height / 2,
    }
  }
  // 没有应用图标时退回到底部中央。
  const parent = rootEl.value?.parentElement
  return {
    x: (parent?.clientWidth ?? window.innerWidth) / 2,
    y: (parent?.clientHeight ?? window.innerHeight) - 24,
  }
}

function applyMinimizeTargetVars() {
  if (!rootEl.value) return
  const target = getTaskbarButtonRect()
  if (target) {
    const windowCenterX = props.x + props.width / 2
    const windowCenterY = props.y + props.height / 2
    rootEl.value.style.setProperty('--minimize-target-x', `${target.x - windowCenterX}px`)
    rootEl.value.style.setProperty('--minimize-target-y', `${target.y - windowCenterY}px`)
  }
}

function handleMinimize() {
  emit('minimize', props.id)
}

function handleTitlebarMouseDown(event: MouseEvent) {
  if ((event.target as HTMLElement).closest('.window-action-buttons')) return
  event.preventDefault()
  windowInteraction.startDrag(event)
}

const currentComponent = computed(() => {
  loadAttempt.value
  const app = getApp(props.appKey)
  if (!app) return null
  return defineAsyncComponent({
    loader: app.entryComponent,
    onError(error, _retry, fail) {
      loadError.value = error?.message || '应用入口组件加载失败'
      console.error(`[DesktopApp] ${props.appKey} failed to load`, error)
      fail()
    },
  })
})

function retryLoad() {
  loadError.value = ''
  loadAttempt.value += 1
}

const windowStyle = computed(() => {
  const style: Record<string, string> = {
    left: `${props.x}px`,
    top: `${props.y}px`,
    width: `${props.width}px`,
    height: `${props.height}px`,
    zIndex: String(props.zIndex),
    '--window-anim-duration': `${animDuration.value}ms`,
  }
  // 打开动画来源坐标
  if (props.animationOrigin && !entered.value) {
    const origin = props.animationOrigin
    const scaleX = origin.width / props.width
    const scaleY = origin.height / props.height
    const translateX = origin.x - props.x + (origin.width - props.width) / 2
    const translateY = origin.y - props.y + (origin.height - props.height) / 2
    style['--origin-translate-x'] = `${translateX}px`
    style['--origin-translate-y'] = `${translateY}px`
    style['--origin-scale-x'] = String(scaleX.toFixed(4))
    style['--origin-scale-y'] = String(scaleY.toFixed(4))
  }
  return style
})

const appInfo = computed(() => getApp(props.appKey))
const isFinderWindow = computed(() => props.appKey === 'files' || props.appKey === 'desktop')
const windowType = computed(() => appInfo.value?.windowType || 'normal')
const resizable = computed(() => appInfo.value?.resizable !== false && windowType.value !== 'fullscreen')
const minWidth = computed(() => appInfo.value?.minWidth ?? 400)
const minHeight = computed(() => appInfo.value?.minHeight ?? 260)
const preMaximizeState = computed(() => props.preMaximizeState)

type FinderTab = {
  id: string
  title: string
  folderId?: number
  folderName?: string
}
const finderTabs = ref<FinderTab[]>([])
const activeFinderTabId = ref('')

function seedFinderTabs() {
  if (!isFinderWindow.value) {
    finderTabs.value = []
    activeFinderTabId.value = ''
    return
  }
  if (finderTabs.value.length) return
  const folderId = props.payload?.folderId as number | undefined
  const folderName = typeof props.payload?.folderName === 'string' ? props.payload.folderName : props.title
  const tab: FinderTab = {
    id: `tab-${props.id}-root`,
    title: folderName || '桌面',
    folderId: folderId as number | undefined,
    folderName: folderName || '桌面',
  }
  finderTabs.value = [tab]
  activeFinderTabId.value = tab.id
}

function addFinderTab() {
  if (!isFinderWindow.value) return
  seedFinderTabs()
  // Finder-like: new tab clones current path (not always desktop)
  const current = activeFinderTab.value
  const folderId = current?.folderId ?? (props.payload?.folderId as number | undefined) ?? 0
  const folderName = current?.folderName
    || (typeof props.payload?.folderName === 'string' ? props.payload.folderName : '')
    || props.title
    || '桌面'
  const tab: FinderTab = {
    id: `tab-${props.id}-${Date.now()}`,
    title: folderName,
    folderId,
    folderName,
  }
  finderTabs.value = [...finderTabs.value, tab]
  activeFinderTabId.value = tab.id
}

function activateFinderTab(tabId: string) {
  if (activeFinderTabId.value === tabId) return
  // snapshot active tab from live payload before switching away
  syncActiveTabFromPayload()
  activeFinderTabId.value = tabId
}

function closeFinderTab(tabId: string) {
  if (finderTabs.value.length <= 1) {
    requestClose()
    return
  }
  const closingActive = activeFinderTabId.value === tabId
  if (closingActive) syncActiveTabFromPayload()
  const idx = finderTabs.value.findIndex((t) => t.id === tabId)
  const next = finderTabs.value.filter((t) => t.id !== tabId)
  finderTabs.value = next
  if (closingActive) {
    const fallback = next[Math.max(0, idx - 1)] || next[0]
    activeFinderTabId.value = fallback.id
  }
}

const activeFinderTab = computed(() => finderTabs.value.find((t) => t.id === activeFinderTabId.value) || null)
const windowTitleText = computed(() => {
  if (!isFinderWindow.value) return props.title
  const tab = activeFinderTab.value
  return tab?.title || tab?.folderName || props.title
})

function syncActiveTabFromPayload() {
  const tab = activeFinderTab.value
  if (!tab) return
  const folderName = typeof props.payload?.folderName === 'string' && props.payload.folderName.trim()
    ? props.payload.folderName.trim()
    : (props.title || tab.title)
  const folderId = props.payload?.folderId as number | undefined
  const idx = finderTabs.value.findIndex((t) => t.id === tab.id)
  if (idx < 0) return
  const next = [...finderTabs.value]
  next[idx] = {
    ...next[idx],
    title: folderName || next[idx].title,
    // only write folderId when payload carries it (avoid wiping on empty)
    folderId: folderId !== undefined ? folderId : next[idx].folderId,
    folderName: folderName || next[idx].folderName,
  }
  finderTabs.value = next
}

const finderComponentBind = computed(() => {
  if (!isFinderWindow.value) return { ...(props.payload || {}), windowId: props.id }
  seedFinderTabs()
  const tab = activeFinderTab.value
  return {
    windowId: props.id,
    // tab-local navigation state must not be overridden by stale window payload
    folderId: tab?.folderId ?? 0,
    folderName: tab?.folderName || '桌面',
  }
})

// only sync the *active* tab from payload updates produced by that tab's navigation
watch(
  () => [isFinderWindow.value, props.payload?.folderId, props.payload?.folderName, props.title] as const,
  () => {
    if (!isFinderWindow.value) return
    if (!finderTabs.value.length) {
      seedFinderTabs()
      return
    }
    syncActiveTabFromPayload()
  },
  { immediate: true },
)

const rootEl = ref<HTMLElement | null>(null)
const windowInteraction = useWindowInteraction(() => ({
  id: props.id, x: props.x, y: props.y, width: props.width, height: props.height, maximized: props.maximized,
  minWidth: minWidth.value, minHeight: minHeight.value, rootEl,
  preMaximizeState: preMaximizeState.value,
  activate: (id) => emit('activate', id), updatePosition: (id, x, y) => emit('update-position', id, x, y),
  updateGeometry: (id, x, y, w, h) => emit('update-geometry', id, x, y, w, h),
  maximize: (id, restoreState) => emit('maximize', id, restoreState),
}))
const snapPreview = windowInteraction.snapPreview
const windowClasses = computed(() => ({
  'desktop-window-active': props.isActive,
  'desktop-window-maximized': props.maximized,
  'desktop-window-fullscreen': windowType.value === 'fullscreen',
  'desktop-window-entered': entered.value,
  'desktop-window-minimized': props.minimized && !minimizing.value && !restoring.value,
  'desktop-window-minimizing': minimizing.value,
  'desktop-window-restoring': restoring.value,
  'desktop-window-closing': closing.value,
  'desktop-window-dragging': windowInteraction.dragging.value,
  'desktop-window-opening-from-origin': openingFromOrigin.value,
  'desktop-window-maximized-transition': props.maximized || entered.value,
}))
const snapPreviewStyle = computed(() => {
  const preview = snapPreview.value
  if (!preview) return {}
  const zIndex = Number.isFinite(props.zIndex) ? props.zIndex + 1 : 1
  return {
    left: `${preview.x}px`,
    top: `${preview.y}px`,
    width: `${preview.width}px`,
    height: `${preview.height}px`,
    zIndex,
  }
})

function requestClose() {
  if (closing.value) return
  closing.value = true
  closeTimer = window.setTimeout(() => emit('close', props.id), animDuration.value)
}

onMounted(() => {
  计入应用活跃()
  if (props.animationOrigin) {
    // 从来源坐标展开的动画
    openingFromOrigin.value = true
    enterFrame = window.requestAnimationFrame(() => {
      entered.value = true
      setTimeout(() => { openingFromOrigin.value = false }, animDuration.value)
    })
  } else {
    // 通用淡入动画
    enterFrame = window.requestAnimationFrame(() => {
      entered.value = true
    })
  }
})

onUnmounted(() => {
  清除空闲卸载定时器()
  释放应用活跃()
  if (enterFrame) window.cancelAnimationFrame(enterFrame)
  if (closeTimer) window.clearTimeout(closeTimer)
  if (minimizeTimer) window.clearTimeout(minimizeTimer)
  if (restoreTimer) window.clearTimeout(restoreTimer)
})
</script>

<style scoped>
/* ═══ 基础窗口状态 ═══ */
.desktop-window {
  position: absolute;
  opacity: 0;
  transform: scale(0.95);
  will-change: transform, opacity;
  transition:
    opacity var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    transform var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 0.16s ease,
    border-color 0.16s ease;
}

/* Finder / 访达：系统标题栏（隐藏应用图标，仅保留居中标题） */
.desktop-window-finder :deep(.window-title-info .app-icon) {
  display: none;
}
.desktop-window-finder :deep(.window-title) {
  font-weight: 600;
  letter-spacing: -0.015em;
  font-size: 13px;
  color: #1d1d1f;
}
.desktop-window-finder:not(.desktop-window-active) :deep(.window-title) {
  color: rgba(60, 60, 67, 0.55);
}
.desktop-window-finder :deep(.window-titlebar) {
  height: 38px;
  border-bottom: 0;
  background: #e8e8ea;
  box-shadow: inset 0 -0.5px 0 rgba(0, 0, 0, 0.08), inset 0 0.5px 0 rgba(255, 255, 255, 0.55);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}
.desktop-window-finder.desktop-window-active :deep(.window-titlebar) {
  background: #f0f0f2;
}
.window-tab-add {
  width: 22px;
  height: 22px;
  margin-right: 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgba(60, 60, 67, 0.75);
  font: 600 16px/1 -apple-system, BlinkMacSystemFont, sans-serif;
  cursor: pointer;
}
.window-tab-add:hover { background: rgba(0, 0, 0, 0.06); }
.window-finder-tabs {
  display: flex;
  gap: 1px;
  align-items: flex-end;
  min-height: 28px;
  padding: 0 10px;
  background: #e5e5e7;
  box-shadow: inset 0 -0.5px 0 rgba(0, 0, 0, 0.08);
  overflow-x: auto;
}
.window-finder-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 160px;
  height: 24px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px 6px 0 0;
  background: transparent;
  color: rgba(60, 60, 67, 0.72);
  font: 500 12px/1 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  cursor: pointer;
}
.window-finder-tab.active {
  background: #ffffff;
  color: #1d1d1f;
  box-shadow: 0 -0.5px 0 rgba(0, 0, 0, 0.06);
}
.window-finder-tab-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.window-finder-tab-close {
  opacity: 0.55;
  font-size: 14px;
  line-height: 1;
}
.window-finder-tab:hover .window-finder-tab-close { opacity: 0.9; }
.desktop-window-finder :deep(.window-content) {
  background: transparent;
}
.desktop-window-finder :deep(.window-content-padding) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.desktop-window-finder :deep(.desktop-file-manager) {
  flex: 1;
  min-height: 0;
}

/* ═══ 打开动画 - 通用（从中心淡入） ═══ */
.desktop-window-entered {
  opacity: 1;
  transform: scale(1);
}

/* ═══ 打开动画 - 从来源坐标展开 ═══ */
.desktop-window-opening-from-origin:not(.desktop-window-entered) {
  opacity: 0;
  transform: translate(var(--origin-translate-x, 0), var(--origin-translate-y, 0))
             scale(var(--origin-scale-x, 0.5), var(--origin-scale-y, 0.5));
}
.desktop-window-opening-from-origin.desktop-window-entered {
  opacity: 1;
  transform: translate(0, 0) scale(1);
}

/* ═══ 关闭动画 ═══ */
.desktop-window-closing {
  opacity: 0;
  transform: scale(0.92);
  pointer-events: none;
  transition:
    opacity var(--window-anim-duration, 200ms) cubic-bezier(0.5, 0, 0.75, 0),
    transform var(--window-anim-duration, 200ms) cubic-bezier(0.5, 0, 0.75, 0);
}

/* ═══ 最小化动画 - genie 近似（飞入 Dock + 纵向压缩） ═══ */
.desktop-window-minimizing {
  opacity: 0;
  transform: translate(var(--minimize-target-x, 0), var(--minimize-target-y, 0)) scale(0.12, 0.04);
  filter: blur(1.2px);
  pointer-events: none;
  transform-origin: 50% 100%;
  transition:
    opacity var(--window-anim-duration, 280ms) cubic-bezier(0.55, 0.05, 0.8, 0.15),
    transform var(--window-anim-duration, 280ms) cubic-bezier(0.55, 0.05, 0.8, 0.15),
    filter var(--window-anim-duration, 280ms) ease;
}

/* ═══ 从 Dock 还原动画 ═══ */
.desktop-window-restoring {
  animation: window-restore-keyframes var(--window-anim-duration, 280ms) cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes window-restore-keyframes {
  from {
    opacity: 0;
    transform: translate(var(--minimize-target-x, 0), var(--minimize-target-y, 0)) scale(0.12, 0.04);
    filter: blur(1.2px);
  }
  70% {
    opacity: 1;
    filter: blur(0);
  }
  to {
    opacity: 1;
    transform: translate(0, 0) scale(1);
    filter: none;
  }
}

/* ═══ 已最小化（动画结束后的静态状态） ═══ */
.desktop-window-minimized {
  opacity: 0;
  transform: translate(var(--minimize-target-x, 0), var(--minimize-target-y, 0)) scale(0.12, 0.04);
  pointer-events: none;
}

/* ═══ 最大化/还原过渡 ═══ */
.desktop-window-maximized-transition {
  transition:
    left var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    top var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    width var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    height var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    border-radius var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    opacity var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    transform var(--window-anim-duration, 200ms) cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 0.16s ease,
    border-color 0.16s ease;
}

.desktop-window-maximized {
  border-radius: var(--window-maximized-radius) !important;
}

/* ═══ 拖拽时禁用过渡 ═══ */
.desktop-window-dragging {
  transition: box-shadow 0.12s ease, border-color 0.12s ease !important;
}

/* ═══ 贴靠预览框 ═══ */
.window-snap-preview {
  position: absolute;
  box-sizing: border-box;
  border: 1px solid rgba(125, 211, 252, 0.92);
  background: rgba(14, 165, 233, 0.18);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.38), 0 14px 38px rgba(15, 23, 42, 0.22);
  pointer-events: none;
  backdrop-filter: blur(4px);
  transition:
    left 0.08s ease,
    top 0.08s ease,
    width 0.08s ease,
    height 0.08s ease,
    opacity 0.08s ease;
}
.window-snap-preview-top { border-radius: 0 0 8px 8px; }
.window-snap-preview-left { border-radius: 0 10px 10px 0; }
.window-snap-preview-right { border-radius: 10px 0 0 10px; }
.window-snap-preview-top-left,
.window-snap-preview-top-right,
.window-snap-preview-bottom-left,
.window-snap-preview-bottom-right { border-radius: 10px; }

/* ═══ 缩放手柄 ═══ */
.resize-handle { position: absolute; z-index: 6; }
.resize-handle-n, .resize-handle-s { left: 10px; right: 10px; height: 8px; cursor: ns-resize; }
.resize-handle-n { top: -4px; }
.resize-handle-s { bottom: -4px; }
.resize-handle-e, .resize-handle-w { top: 10px; bottom: 10px; width: 8px; cursor: ew-resize; }
.resize-handle-e { right: -4px; }
.resize-handle-w { left: -4px; }
.resize-handle-ne, .resize-handle-sw { width: 14px; height: 14px; cursor: nesw-resize; }
.resize-handle-nw, .resize-handle-se { width: 14px; height: 14px; cursor: nwse-resize; }
.resize-handle-ne { top: -4px; right: -4px; }
.resize-handle-nw { top: -4px; left: -4px; }
.resize-handle-se { right: 1px; bottom: 1px; }
.resize-handle-sw { left: -4px; bottom: -4px; }
.resize-handle-se::after {
  content: "";
  position: absolute;
  right: 1px;
  bottom: 1px;
  width: 7px;
  height: 7px;
  border-right: 2px solid rgba(100, 116, 139, 0.55);
  border-bottom: 2px solid rgba(100, 116, 139, 0.55);
  border-radius: 0 0 3px 0;
}

/* ═══ 无障碍：减弱动画偏好 ═══ */
@media (prefers-reduced-motion: reduce) {
  .desktop-window,
  .desktop-window-maximized-transition,
  .window-snap-preview {
    transition: none !important;
    animation: none !important;
  }
}
</style>
