<template>
  <div class="fm-path-bar" role="navigation" aria-label="路径">
    <button
      v-for="(crumb, index) in crumbs"
      :key="`${crumb.id ?? 'root'}-${index}`"
      type="button"
      class="fm-path-item"
      :class="{ active: index === crumbs.length - 1 }"
      @click="$emit('navigate', index)"
    >
      <span class="fm-path-icon" aria-hidden="true">{{ index === 0 ? '🖥️' : '📁' }}</span>
      <span class="fm-path-label">{{ crumb.name }}</span>
      <span v-if="index < crumbs.length - 1" class="fm-path-sep" aria-hidden="true">›</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { DesktopFileManagerBreadcrumbItem } from './types'

defineProps<{
  crumbs: DesktopFileManagerBreadcrumbItem[]
}>()

defineEmits<{
  (e: 'navigate', index: number): void
}>()
</script>

<style scoped>
.fm-path-bar {
  display: flex;
  align-items: center;
  gap: 0;
  min-height: 24px;
  padding: 0 10px;
  overflow-x: auto;
  background: color-mix(in srgb, #f6f6f8 88%, white);
  box-shadow: inset 0 0.5px 0 rgba(60, 60, 67, 0.12);
  white-space: nowrap;
}

.fm-path-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  border: 0;
  background: transparent;
  color: var(--mac-app-text-secondary, #6e6e73);
  font: 400 11px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  cursor: pointer;
  padding: 0 2px;
}

.fm-path-item:hover {
  color: var(--mac-app-accent, #0a84ff);
}

.fm-path-item.active {
  color: var(--mac-app-text, #1d1d1f);
  font-weight: 600;
}

.fm-path-icon {
  font-size: 11px;
  line-height: 1;
}

.fm-path-sep {
  margin-left: 4px;
  color: rgba(60, 60, 67, 0.35);
  font-weight: 500;
}
</style>
