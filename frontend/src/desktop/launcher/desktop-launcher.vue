<template>
  <Teleport to="body">
    <Transition name="launchpad-fade">
      <div v-if="show" class="launchpad-overlay" @mousedown.self="emit('close')" @keydown.esc="emit('close')">
        <section class="launcher-panel desktop-launcher-panel" role="dialog" aria-label="Launchpad">
          <div class="launchpad-search">
            <Search :size="15" />
            <input
              ref="searchInputRef"
              v-model="searchText"
              class="launcher-search-input desktop-launcher-search-input"
              type="search"
              placeholder="搜索应用"
              aria-label="搜索应用"
              @keydown.escape="handleEscape"
            >
          </div>
          <div class="launchpad-body">
            <template v-if="!searchText.trim() && groupedApps.length">
              <section v-for="group in groupedApps" :key="group.name" class="launchpad-group">
                <h3 class="launchpad-group-title">{{ group.name }}</h3>
                <div class="launchpad-grid desktop-launcher-grid" aria-label="应用">
                  <button
                    v-for="app in group.apps"
                    :key="app.appKey"
                    class="launcher-pinned-item desktop-launcher-app-item"
                    type="button"
                    @click="openApp(app.appKey)"
                  >
                    <AppIcon :icon="app.icon" :app-key="app.appKey" :size="58" />
                    <span>{{ app.appName }}</span>
                  </button>
                </div>
              </section>
            </template>
            <div v-else class="launchpad-grid desktop-launcher-grid" aria-label="应用">
              <button
                v-for="app in filteredApps"
                :key="app.appKey"
                class="launcher-pinned-item desktop-launcher-app-item"
                type="button"
                @click="openApp(app.appKey)"
              >
                <AppIcon :icon="app.icon" :app-key="app.appKey" :size="58" />
                <span>{{ app.appName }}</span>
              </button>
            </div>
            <div v-if="!filteredApps.length" class="launchpad-empty">没有匹配的应用</div>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import AppIcon from '@/desktop/components/app-icon.vue'

const props = defineProps<{ show: boolean; appList: AppRegistryEntry[] }>()
const emit = defineEmits<{ openApp: [appKey: string]; close: []; executeCommand: [command: string] }>()
const searchText = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)

const filteredApps = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return props.appList.filter(app => (
    app.windowType !== 'background-service'
    && (!query || `${app.appName} ${app.description}`.toLocaleLowerCase().includes(query))
  ))
})

const groupedApps = computed(() => {
  const map = new Map<string, AppRegistryEntry[]>()
  for (const app of filteredApps.value) {
    const name = (app.category || '其他').trim() || '其他'
    const list = map.get(name) || []
    list.push(app)
    map.set(name, list)
  }
  return [...map.entries()]
    .map(([name, apps]) => ({
      name,
      apps: [...apps].sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.appName.localeCompare(b.appName, 'zh-CN')),
    }))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
})

watch(() => props.show, (show) => {
  if (!show) return
  searchText.value = ''
  nextTick(() => searchInputRef.value?.focus())
})

function openApp(appKey: string) {
  emit('openApp', appKey)
  emit('close')
}
function handleEscape() {
  if (searchText.value) searchText.value = ''
  else emit('close')
}
</script>

<style scoped>
.launchpad-overlay{position:fixed;inset:0;z-index:var(--z-launchpad);display:flex;align-items:center;justify-content:center;background:rgba(7,17,28,.18);backdrop-filter:var(--desktop-lg-filter,blur(34px) saturate(182%));-webkit-backdrop-filter:var(--desktop-lg-filter,blur(34px) saturate(182%))}
.launcher-panel{width:min(1040px,calc(100vw - 48px));height:min(720px,calc(100vh - 72px));display:flex;flex-direction:column;align-items:center;padding:54px 48px 28px;color:white;text-shadow:0 1px 3px rgba(0,0,0,.35)}
.launchpad-search{width:min(260px,100%);height:30px;display:flex;align-items:center;gap:7px;padding:0 10px;margin-bottom:28px;border:1px solid rgba(255,255,255,.28);border-radius:10px;background:rgba(255,255,255,.16);box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 8px 24px rgba(0,0,0,.12);backdrop-filter:var(--desktop-lg-filter-soft,blur(24px) saturate(160%));-webkit-backdrop-filter:var(--desktop-lg-filter-soft,blur(24px) saturate(160%))}
.launcher-search-input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:white;font:var(--desktop-font-body)}
.launcher-search-input::placeholder{color:rgba(255,255,255,.72)}
.launchpad-body{width:100%;flex:1;min-height:0;overflow:auto}
.launchpad-group{width:100%;margin-bottom:22px}
.launchpad-group-title{margin:0 8px 12px;font:600 13px/1.2 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:rgba(255,255,255,.78);text-align:left;text-shadow:0 1px 2px rgba(0,0,0,.35)}
.launchpad-grid{width:100%;display:grid;grid-template-columns:repeat(6,minmax(96px,1fr));gap:30px 22px;align-content:start;padding:6px 8px}
.launcher-pinned-item{height:102px;border:0;background:transparent;color:white;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;gap:8px;border-radius:12px;font:var(--desktop-font-body);text-shadow:0 1px 3px rgba(0,0,0,.55);transition:transform var(--desktop-duration-fast) var(--desktop-ease-standard)}
.launcher-pinned-item:hover{transform:scale(1.06)}
.launcher-pinned-item:active{transform:scale(.96)}
.launcher-pinned-item:focus-visible{outline:2px solid rgba(255,255,255,.9);outline-offset:4px}
.launcher-pinned-item span{max-width:112px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.launchpad-empty{margin:auto;color:rgba(255,255,255,.72)}
.launchpad-fade-enter-active,.launchpad-fade-leave-active{transition:opacity var(--desktop-duration-standard) var(--desktop-ease-standard)}
.launchpad-fade-enter-from,.launchpad-fade-leave-to{opacity:0}
@media(max-width:900px){.launchpad-grid{grid-template-columns:repeat(4,minmax(84px,1fr));gap:24px 14px}.launcher-panel{padding-inline:24px}}
@media(max-width:620px){.launchpad-grid{grid-template-columns:repeat(3,minmax(76px,1fr))}}
@media(prefers-reduced-motion:reduce){.launchpad-fade-enter-active,.launchpad-fade-leave-active,.launcher-pinned-item{transition:none}.launcher-pinned-item:hover,.launcher-pinned-item:active{transform:none}}
@media(prefers-contrast:more),(prefers-reduced-transparency:reduce){.launchpad-overlay{background:rgba(7,17,28,.94);backdrop-filter:none;-webkit-backdrop-filter:none}}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){.launchpad-overlay{background:rgba(7,17,28,.94)}}
</style>
