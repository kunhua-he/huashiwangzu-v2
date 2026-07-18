<template>
  <header class="fm-navigation-bar">
    <div class="fm-nav-left">
      <button
        class="fm-icon-button"
        type="button"
        :disabled="!canGoBack"
        title="后退"
        aria-label="后退"
        @click="$emit('go-back')"
      >
        <ChevronLeft :size="17" :stroke-width="2" />
      </button>
      <button
        class="fm-icon-button"
        type="button"
        :disabled="!canGoForward"
        title="前进"
        aria-label="前进"
        @click="$emit('go-forward')"
      >
        <ChevronRight :size="17" :stroke-width="2" />
      </button>
    </div>

    <div class="fm-view-switch" role="group" aria-label="视图">
      <span class="fm-view-thumb" :class="`is-${viewMode}`" aria-hidden="true" />
      <button
        type="button"
        class="fm-view-btn"
        :class="{ active: viewMode === 'grid' }"
        title="图标"
        aria-label="图标视图"
        @click="$emit('update:viewMode', 'grid')"
      >
        <LayoutGrid :size="15" :stroke-width="2" />
      </button>
      <button
        type="button"
        class="fm-view-btn"
        :class="{ active: viewMode === 'list' }"
        title="列表"
        aria-label="列表视图"
        @click="$emit('update:viewMode', 'list')"
      >
        <List :size="15" :stroke-width="2" />
      </button>
    </div>

    <div class="fm-toolbar-spacer" />

    <div class="fm-search-pill">
      <Search class="fm-search-icon" :size="13" :stroke-width="2" />
      <input
        class="fm-search-input"
        type="text"
        placeholder="搜索"
        spellcheck="false"
        :value="searchKeyword"
        @input="$emit('update:searchKeyword', ($event.target as HTMLInputElement).value)"
      />
    </div>
  </header>
</template>

<script setup lang="ts">
import { ChevronLeft, ChevronRight, LayoutGrid, List, Search } from 'lucide-vue-next'
import type { DesktopFileManagerBreadcrumbItem } from './types'

defineProps<{
  canGoBack: boolean
  canGoForward: boolean
  canGoUp: boolean
  breadcrumb: DesktopFileManagerBreadcrumbItem[]
  searchKeyword: string
  viewMode: 'grid' | 'list'
}>()

defineEmits<{
  (e: 'go-back'): void
  (e: 'go-forward'): void
  (e: 'go-up'): void
  (e: 'go-root'): void
  (e: 'navigate', index: number): void
  (e: 'update:searchKeyword', value: string): void
  (e: 'update:viewMode', mode: 'grid' | 'list'): void
}>()
</script>

<style scoped>
.fm-navigation-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  min-width: 0;
  height: 44px;
  min-height: 44px;
  padding: 0 12px;
  box-sizing: border-box;
  background: transparent;
  box-shadow: inset 0 -0.5px 0 var(--mac-app-border, rgba(60, 60, 67, 0.18));
}

.fm-nav-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.fm-icon-button {
  width: 30px;
  height: 26px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--mac-app-text-secondary, #6e6e73);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.fm-icon-button:hover:not(:disabled) {
  background: color-mix(in srgb, var(--mac-app-text, #1d1d1f) 7%, transparent);
  color: var(--mac-app-text, #1d1d1f);
}

.fm-icon-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.fm-view-switch {
  position: relative;
  display: flex;
  align-items: center;
  margin: 0 8px;
  padding: 2px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--mac-app-text-secondary, #8e8e93) 16%, transparent);
  box-shadow: inset 0 0 0 0.5px var(--mac-app-border, rgba(60, 60, 67, 0.16));
  flex-shrink: 0;
}

.fm-view-thumb {
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 2px;
  width: 30px;
  border-radius: 7px;
  background: color-mix(in srgb, white 92%, #f2f2f7);
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.18),
    inset 0 0 0 0.5px var(--mac-app-border, rgba(60, 60, 67, 0.14));
  transition: left 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
  pointer-events: none;
}

.fm-view-thumb.is-list {
  left: 32px;
}

.fm-view-btn {
  position: relative;
  z-index: 1;
  width: 30px;
  height: 24px;
  border: 0;
  background: transparent;
  color: var(--mac-app-text-secondary, #6e6e73);
  display: grid;
  place-items: center;
  cursor: pointer;
  border-radius: 7px;
}

.fm-view-btn.active {
  color: var(--mac-app-text, #1d1d1f);
}

.fm-toolbar-spacer {
  flex: 1;
  min-width: 8px;
}

.fm-search-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 180px;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: color-mix(in srgb, white 62%, rgba(246, 246, 248, 0.55));
  box-shadow:
    inset 0 0 0 0.5px var(--mac-app-border, rgba(60, 60, 67, 0.16)),
    0 1px 1px rgba(255, 255, 255, 0.35) inset;
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  flex-shrink: 0;
}

.fm-search-icon {
  color: var(--mac-app-text-secondary, #8e8e93);
  flex-shrink: 0;
}

.fm-search-input {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--mac-app-text, #1d1d1f);
}

.fm-search-input::placeholder {
  color: var(--mac-app-text-secondary, #8e8e93);
}

@media (max-width: 720px) {
  .fm-search-pill {
    width: min(180px, 34vw);
  }
}
</style>
