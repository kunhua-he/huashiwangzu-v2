<template>
  <Teleport to="body">
    <Transition name="launchpad-fade">
      <div
        v-if="show"
        ref="overlayRef"
        class="launchpad-overlay"
        role="dialog"
        aria-label="Launchpad"
        @mousedown.self="emit('close')"
        @keydown="onKeydown"
      >
        <!-- 顶部搜索：现代 macOS 是居中深色胶囊，不是白玻璃条 -->
        <div class="launchpad-search-wrap">
          <div class="launchpad-search">
            <Search class="launchpad-search-icon" :size="13" :stroke-width="2.2" />
            <input
              ref="searchInputRef"
              v-model="searchText"
              class="launchpad-search-input"
              type="search"
              placeholder="搜索"
              aria-label="搜索"
              autocomplete="off"
              spellcheck="false"
              @keydown.escape.prevent="handleEscape"
            >
          </div>
        </div>

        <!-- 分页网格：无分组标题，纯图标墙 -->
        <div
          ref="pagesRef"
          class="launchpad-pages"
          @pointerdown="onPagePointerDown"
          @pointermove="onPagePointerMove"
          @pointerup="onPagePointerUp"
          @pointercancel="onPagePointerUp"
          @wheel.prevent="onWheel"
        >
          <div
            class="launchpad-pages-track"
            :style="trackStyle"
          >
            <div
              v-for="(page, pageIndex) in pages"
              :key="pageIndex"
              class="launchpad-page"
            >
              <div class="launchpad-grid">
                <button
                  v-for="app in page"
                  :key="app.appKey"
                  class="launchpad-app"
                  type="button"
                  :aria-label="app.appName"
                  @click="openApp(app.appKey)"
                >
                  <AppIcon :icon="app.icon" :app-key="app.appKey" :size="iconSize" />
                  <span class="launchpad-app-name">{{ app.appName }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!filteredApps.length" class="launchpad-empty">没有匹配的应用</div>

        <!-- 底部分页点 -->
        <div v-if="pages.length > 1 && !searchText.trim()" class="launchpad-dots" role="tablist" aria-label="Launchpad 页面">
          <button
            v-for="(_, pageIndex) in pages"
            :key="pageIndex"
            class="launchpad-dot"
            type="button"
            role="tab"
            :aria-selected="pageIndex === currentPage"
            :class="{ 'is-active': pageIndex === currentPage }"
            :aria-label="`第 ${pageIndex + 1} 页`"
            @click="goPage(pageIndex)"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import AppIcon from '@/desktop/components/app-icon.vue'

/** 每页约 5 行 × 7 列，接近现代 Launchpad 密度 */
const COLS = 7
const ROWS = 5
const PER_PAGE = COLS * ROWS

const props = defineProps<{ show: boolean; appList: AppRegistryEntry[] }>()
const emit = defineEmits<{ openApp: [appKey: string]; close: []; executeCommand: [command: string] }>()

const searchText = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)
const overlayRef = ref<HTMLElement | null>(null)
const pagesRef = ref<HTMLElement | null>(null)
const currentPage = ref(0)
const dragOffset = ref(0)
const dragging = ref(false)
const iconSize = ref(72)

let pointerStartX = 0
let pointerActive = false
let reducedMotion = false

const filteredApps = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return props.appList
    .filter(app => (
      app.windowType !== 'background-service'
      && (!query || `${app.appName} ${app.description || ''} ${app.appKey}`.toLocaleLowerCase().includes(query))
    ))
    .slice()
    .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.appName.localeCompare(b.appName, 'zh-CN'))
})

/** 搜索时单页展示全部结果；否则按页切片 */
const pages = computed(() => {
  const apps = filteredApps.value
  if (!apps.length) return [[]] as AppRegistryEntry[][]
  if (searchText.value.trim()) return [apps]
  const result: AppRegistryEntry[][] = []
  for (let i = 0; i < apps.length; i += PER_PAGE) {
    result.push(apps.slice(i, i + PER_PAGE))
  }
  return result.length ? result : [[]]
})

const trackStyle = computed(() => {
  const page = currentPage.value
  const offset = dragOffset.value
  const x = `calc(${-page * 100}% + ${offset}px)`
  return {
    transform: `translate3d(${x}, 0, 0)`,
    transition: dragging.value || reducedMotion ? 'none' : 'transform 320ms cubic-bezier(.22, 1, .36, 1)',
  }
})

function goPage(index: number) {
  const max = Math.max(0, pages.value.length - 1)
  currentPage.value = Math.max(0, Math.min(max, index))
  dragOffset.value = 0
  dragging.value = false
}

function openApp(appKey: string) {
  emit('openApp', appKey)
  emit('close')
}

function handleEscape() {
  if (searchText.value) searchText.value = ''
  else emit('close')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    handleEscape()
    return
  }
  if (searchText.value.trim()) return
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    goPage(currentPage.value + 1)
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    goPage(currentPage.value - 1)
  }
}

function onPagePointerDown(event: PointerEvent) {
  if (searchText.value.trim() || pages.value.length <= 1) return
  if ((event.target as HTMLElement | null)?.closest('button.launchpad-app')) return
  pointerActive = true
  pointerStartX = event.clientX
  dragging.value = true
  dragOffset.value = 0
  pagesRef.value?.setPointerCapture?.(event.pointerId)
}

function onPagePointerMove(event: PointerEvent) {
  if (!pointerActive) return
  dragOffset.value = event.clientX - pointerStartX
}

function onPagePointerUp(event: PointerEvent) {
  if (!pointerActive) return
  pointerActive = false
  const delta = dragOffset.value
  dragging.value = false
  dragOffset.value = 0
  try { pagesRef.value?.releasePointerCapture?.(event.pointerId) } catch { /* ignore */ }
  if (Math.abs(delta) > 64) {
    goPage(currentPage.value + (delta < 0 ? 1 : -1))
  }
}

function onWheel(event: WheelEvent) {
  if (searchText.value.trim() || pages.value.length <= 1) return
  // 触控板横向 / 明显横向滚轮切页
  if (Math.abs(event.deltaX) > Math.abs(event.deltaY) && Math.abs(event.deltaX) > 18) {
    goPage(currentPage.value + (event.deltaX > 0 ? 1 : -1))
  }
}

function updateIconSize() {
  const w = window.innerWidth
  if (w < 700) iconSize.value = 56
  else if (w < 1100) iconSize.value = 64
  else iconSize.value = 72
}

watch(() => props.show, (show) => {
  if (!show) {
    searchText.value = ''
    currentPage.value = 0
    dragOffset.value = 0
    dragging.value = false
    return
  }
  searchText.value = ''
  currentPage.value = 0
  updateIconSize()
  nextTick(() => {
    searchInputRef.value?.focus({ preventScroll: true })
    overlayRef.value?.focus?.()
  })
})

watch(searchText, () => {
  currentPage.value = 0
})

watch(pages, (list) => {
  if (currentPage.value >= list.length) currentPage.value = Math.max(0, list.length - 1)
})

function onResize() {
  updateIconSize()
}

if (typeof window !== 'undefined') {
  reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
  window.addEventListener('resize', onResize)
}

onUnmounted(() => {
  if (typeof window !== 'undefined') window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
/* 全屏 Launchpad：毛玻璃盖住桌面，不是居中面板 */
.launchpad-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-launchpad);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding:
    max(52px, calc(var(--desktop-menu-bar-height, 28px) + 28px))
    24px
    28px;
  color: #fff;
  background: rgba(20, 22, 28, 0.28);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  backdrop-filter: blur(28px) saturate(140%);
  outline: none;
  user-select: none;
}

.launchpad-search-wrap {
  flex: 0 0 auto;
  width: 100%;
  display: flex;
  justify-content: center;
  margin-bottom: 28px;
}

/* 现代 macOS：小而扁的深色搜索胶囊 */
.launchpad-search {
  width: min(240px, 72vw);
  height: 28px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border-radius: 8px;
  border: 0.5px solid rgba(255, 255, 255, 0.14);
  background: rgba(0, 0, 0, 0.22);
  box-shadow: inset 0 0.5px 0 rgba(255, 255, 255, 0.08);
  -webkit-backdrop-filter: blur(16px) saturate(120%);
  backdrop-filter: blur(16px) saturate(120%);
}
.launchpad-search-icon {
  flex: 0 0 auto;
  opacity: 0.72;
  color: rgba(255, 255, 255, 0.88);
}
.launchpad-search-input {
  min-width: 0;
  flex: 1;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: rgba(255, 255, 255, 0.96);
  font: 400 13px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  letter-spacing: -0.01em;
}
.launchpad-search-input::placeholder {
  color: rgba(255, 255, 255, 0.55);
}
.launchpad-search-input::-webkit-search-cancel-button {
  -webkit-appearance: none;
  appearance: none;
}

.launchpad-pages {
  width: min(1100px, 100%);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  touch-action: pan-y;
  cursor: default;
}
.launchpad-pages-track {
  height: 100%;
  display: flex;
  will-change: transform;
}
.launchpad-page {
  flex: 0 0 100%;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 4px 8px 12px;
  box-sizing: border-box;
}

/* 固定 7 列网格，无分组标题 */
.launchpad-grid {
  width: 100%;
  max-width: 1040px;
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  grid-auto-rows: minmax(112px, auto);
  gap: 18px 10px;
  align-content: start;
  justify-items: center;
}

.launchpad-app {
  width: 100%;
  max-width: 112px;
  border: 0;
  padding: 6px 4px 2px;
  background: transparent;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  border-radius: 12px;
  cursor: default;
  transition: transform 140ms cubic-bezier(.22, 1, .36, 1), background 120ms ease;
}
.launchpad-app:hover {
  transform: scale(1.06);
}
.launchpad-app:active {
  transform: scale(0.94);
}
.launchpad-app:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.85);
  outline-offset: 4px;
}
.launchpad-app-name {
  max-width: 100%;
  padding: 0 2px;
  font: 400 12px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  letter-spacing: -0.01em;
  text-align: center;
  color: rgba(255, 255, 255, 0.96);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.launchpad-empty {
  position: absolute;
  left: 50%;
  top: 46%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.72);
  font: 400 15px/1.4 -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  pointer-events: none;
}

/* 底部分页点 */
.launchpad-dots {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 22px;
  margin-top: 8px;
}
.launchpad-dot {
  width: 7px;
  height: 7px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.32);
  cursor: default;
  transition: background 140ms ease, transform 140ms ease;
}
.launchpad-dot.is-active {
  background: rgba(255, 255, 255, 0.92);
  transform: scale(1.08);
}
.launchpad-dot:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.8);
  outline-offset: 3px;
}

.launchpad-fade-enter-active,
.launchpad-fade-leave-active {
  transition: opacity 220ms cubic-bezier(.22, 1, .36, 1);
}
.launchpad-fade-enter-from,
.launchpad-fade-leave-to {
  opacity: 0;
}

@media (max-width: 1100px) {
  .launchpad-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 16px 8px;
  }
}
@media (max-width: 860px) {
  .launchpad-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
  .launchpad-overlay {
    padding-inline: 16px;
  }
}
@media (max-width: 640px) {
  .launchpad-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-auto-rows: minmax(100px, auto);
  }
  .launchpad-app-name {
    font-size: 11px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .launchpad-fade-enter-active,
  .launchpad-fade-leave-active,
  .launchpad-app,
  .launchpad-pages-track {
    transition: none !important;
  }
  .launchpad-app:hover,
  .launchpad-app:active {
    transform: none;
  }
}
@media (prefers-reduced-transparency: reduce), (prefers-contrast: more) {
  .launchpad-overlay {
    background: rgba(18, 20, 26, 0.94);
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
  .launchpad-search {
    background: rgba(0, 0, 0, 0.45);
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .launchpad-overlay {
    background: rgba(18, 20, 26, 0.94);
  }
}
</style>
