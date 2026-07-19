<template>
  <Teleport to="body">
    <Transition name="spotlight-fade">
      <div v-if="show" class="spotlight-overlay" @mousedown.self="emit('close')">
        <section class="spotlight-panel glass-spotlight" role="dialog" aria-label="Spotlight">
          <div class="spotlight-search-row">
            <Search :size="24" />
            <input
              ref="inputRef"
              v-model="searchText"
              class="spotlight-input"
              type="search"
              placeholder="Spotlight 搜索应用、文件、设置"
              aria-label="Spotlight 搜索"
              @keydown.escape="emit('close')"
              @keydown.down.prevent="moveSelection(1)"
              @keydown.up.prevent="moveSelection(-1)"
              @keydown.enter.prevent="executeSelected"
            />
            <kbd>esc</kbd>
          </div>
          <div v-if="searching" class="spotlight-empty">正在搜索文件…</div>
          <div v-else-if="results.length" class="spotlight-results" role="listbox">
            <button
              v-for="(item, index) in results"
              :key="item.id"
              class="spotlight-result"
              :class="{ 'is-selected': index === selectedIndex }"
              type="button"
              role="option"
              :aria-selected="index === selectedIndex"
              @mouseenter="selectedIndex = index"
              @click="execute(item)"
            >
              <span v-if="systemIcon(item)" class="spotlight-system-icon">
                <component :is="systemIcon(item)" :size="22" :stroke-width="1.8" />
              </span>
              <AppIcon v-else :icon="item.icon || fallbackIcon(item.type)" :app-key="resultAppKey(item)" :size="34" />
              <span class="spotlight-result-copy">
                <strong>{{ item.title }}</strong>
                <small>{{ item.description || resultKindLabel(item.type) }}</small>
              </span>
              <span class="spotlight-kind">{{ resultKindLabel(item.type) }}</span>
            </button>
          </div>
          <div v-else-if="searchText.trim()" class="spotlight-empty">没有找到结果</div>
          <div v-else class="spotlight-empty">输入应用、文件或命令 · 下方为最近使用</div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { FileText, Folder, LogOut, Maximize2, Minimize2, RefreshCw, Search, Settings } from 'lucide-vue-next'
import AppIcon from '@/desktop/components/app-icon.vue'
import { commandRegistry, type SearchResultItem } from '@/desktop/app-registry/command-registry'
import { searchFilesRequest } from '@/shared/api/desktop'
import { formatFileDisplayName } from '@/shared/files/display-name'
import { openAppById, openFileByRecord } from '@/desktop/app-registry/app-opener'
import { 读取通用缓存, 写入通用缓存 } from '@/desktop/runtime'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: [] }>()
const searchText = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const selectedIndex = ref(0)
const searching = ref(false)
const remoteFiles = ref<SearchResultItem[]>([])
const RECENT_KEY = 'desktop.spotlight.recent.v1'
const recentIds = ref<string[]>([])
let searchToken = 0
let searchTimer: ReturnType<typeof setTimeout> | null = null

function loadRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    recentIds.value = raw ? JSON.parse(raw) as string[] : []
  } catch {
    recentIds.value = []
  }
}
function pushRecent(id: string) {
  recentIds.value = [id, ...recentIds.value.filter((x) => x !== id)].slice(0, 8)
  localStorage.setItem(RECENT_KEY, JSON.stringify(recentIds.value))
}

const localResults = computed(() => {
  const q = searchText.value.trim()
  if (q) return commandRegistry.search(q).slice(0, 8)
  const all = commandRegistry.search('')
  const byId = new Map(all.map((item) => [item.id, item]))
  const recent = recentIds.value.map((id) => byId.get(id)).filter(Boolean) as SearchResultItem[]
  const fallback = all.filter((item) => item.type === 'command' || item.type === 'app').slice(0, 6)
  const merged = [...recent]
  for (const item of fallback) {
    if (!merged.some((x) => x.id === item.id)) merged.push(item)
  }
  // 设置类快捷入口
  const settingsHints: SearchResultItem[] = [
    {
      id: 'hint:settings-desktop',
      type: 'command',
      title: '桌面与 Dock 设置',
      description: '壁纸、低内存、快捷键',
      icon: 'Settings',
      matchField: 'title',
      execute: () => openAppById('settings'),
    },
  ]
  for (const item of settingsHints) {
    if (!merged.some((x) => x.id === item.id)) merged.push(item)
  }
  return merged.slice(0, 9)
})

const results = computed(() => {
  const q = searchText.value.trim()
  if (!q) return localResults.value
  const merged = [...localResults.value]
  for (const item of remoteFiles.value) {
    if (!merged.some((x) => x.id === item.id)) merged.push(item)
  }
  return merged.slice(0, 12)
})

async function runRemoteFileSearch(q: string) {
  const token = ++searchToken
  if (!q || q.length < 1) {
    remoteFiles.value = []
    searching.value = false
    return
  }
  const cacheKey = `spotlight:files:${q.toLowerCase()}`
  const cached = 读取通用缓存<SearchResultItem[]>(cacheKey)
  if (cached?.length) {
    remoteFiles.value = cached
  }
  searching.value = true
  try {
    const page = await searchFilesRequest(q, undefined, 1, 12, { recursive: true })
    if (token !== searchToken) return
    const items: SearchResultItem[] = (page.items || []).map((file) => {
      const title = file.is_folder
        ? String(file.file_name || '')
        : formatFileDisplayName(file.file_name, file.format)
      return {
        id: `remote-file:${file.id}`,
        type: 'file',
        title,
        description: file.is_folder
          ? '文件夹 · 全库搜索'
          : `${String(file.format || '文件').toUpperCase()} · 全库搜索`,
        icon: file.is_folder ? 'Folder' : 'Document',
        matchField: 'title',
        execute: () => {
          if (file.is_folder || !file.format) {
            openAppById('desktop', { folderId: file.id, folderName: title })
          } else {
            openFileByRecord({
              fileId: file.id,
              fileName: title,
              format: file.format || '',
            })
          }
        },
      }
    })
    remoteFiles.value = items
    写入通用缓存(cacheKey, items)
  } catch {
    if (token === searchToken) {
      // 保留本地结果；远程失败静默
      if (!cached?.length) remoteFiles.value = []
    }
  } finally {
    if (token === searchToken) searching.value = false
  }
}

watch(() => props.show, (show) => {
  if (!show) {
    if (searchTimer) clearTimeout(searchTimer)
    searching.value = false
    remoteFiles.value = []
    return
  }
  searchText.value = ''
  selectedIndex.value = 0
  remoteFiles.value = []
  loadRecent()
  nextTick(() => inputRef.value?.focus())
})

watch(searchText, (value) => {
  selectedIndex.value = 0
  if (searchTimer) clearTimeout(searchTimer)
  const q = value.trim()
  if (!q) {
    remoteFiles.value = []
    searching.value = false
    return
  }
  searchTimer = setTimeout(() => { void runRemoteFileSearch(q) }, 220)
})

watch(results, () => { selectedIndex.value = 0 })

function moveSelection(delta: number) {
  if (!results.value.length) return
  selectedIndex.value = (selectedIndex.value + delta + results.value.length) % results.value.length
}
function executeSelected() {
  const item = results.value[selectedIndex.value]
  if (item) execute(item)
}
function execute(item: SearchResultItem) {
  pushRecent(item.id)
  void item.execute()
  emit('close')
}
function fallbackIcon(type: SearchResultItem['type']) {
  return type === 'file' ? 'Document' : type === 'app' ? 'Grid' : 'Search'
}
function resultAppKey(item: SearchResultItem) {
  return item.id.startsWith('app:') ? item.id.split(':')[1] : ''
}
const systemIcons = { Document: FileText, Folder, LogOut, Maximize2, Minimize2, RefreshCw, Settings }
function systemIcon(item: SearchResultItem) {
  return item.type === 'app' || item.type === 'background-capability'
    ? null
    : systemIcons[item.icon as keyof typeof systemIcons] || Search
}
function resultKindLabel(type: SearchResultItem['type']) {
  return type === 'app' ? '应用' : type === 'file' ? '文件' : type === 'background-capability' ? '后台能力' : '命令'
}
</script>

<style scoped>
.spotlight-overlay{position:fixed;inset:0;z-index:var(--z-spotlight);display:flex;justify-content:center;align-items:flex-start;padding-top:min(18vh,160px);background:rgba(4,9,18,.08)}
.spotlight-panel{width:min(680px,calc(100vw - 32px));overflow:hidden;color:var(--desktop-ink)}
.spotlight-search-row{height:64px;display:flex;align-items:center;gap:13px;padding:0 18px;border-bottom:1px solid var(--desktop-divider)}.spotlight-input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font-size:22px;font-family:inherit}.spotlight-input::placeholder{color:var(--desktop-ink-muted)}.spotlight-search-row kbd{padding:2px 6px;border:1px solid var(--desktop-divider);border-radius:5px;color:var(--desktop-ink-muted);font:var(--desktop-font-caption)}
.spotlight-results{padding:7px;max-height:min(480px,60vh);overflow:auto}.spotlight-result{width:100%;height:54px;display:flex;align-items:center;gap:11px;padding:0 10px;border:0;border-radius:9px;background:transparent;color:inherit;text-align:left}.spotlight-result.is-selected{background:var(--desktop-selection);color:white}.spotlight-system-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:8px;background:rgba(60,60,67,.1);flex:0 0 34px}.spotlight-result.is-selected .spotlight-system-icon{background:rgba(255,255,255,.2)}.spotlight-result-copy{min-width:0;flex:1;display:flex;flex-direction:column}.spotlight-result-copy strong{font:var(--desktop-font-body);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.spotlight-result-copy small{font:var(--desktop-font-caption);opacity:.68;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.spotlight-kind{font:var(--desktop-font-caption);opacity:.7}.spotlight-empty{padding:34px;text-align:center;color:var(--desktop-ink-muted);font:var(--desktop-font-body)}
.spotlight-fade-enter-active,.spotlight-fade-leave-active{transition:opacity var(--desktop-duration-standard) var(--desktop-ease-standard)}.spotlight-fade-enter-from,.spotlight-fade-leave-to{opacity:0}.spotlight-fade-enter-active .spotlight-panel{transition:transform var(--desktop-duration-standard) var(--desktop-ease-standard),opacity var(--desktop-duration-fast)}.spotlight-fade-enter-from .spotlight-panel{transform:scale(.96) translateY(-10px);opacity:0}
@media(prefers-reduced-motion:reduce){.spotlight-fade-enter-active,.spotlight-fade-leave-active,.spotlight-fade-enter-active .spotlight-panel{transition:none}}
html.desktop-low-memory .spotlight-panel{backdrop-filter:none;-webkit-backdrop-filter:none}
</style>
