<template>
  <aside class="fm-nav-pane">
    <div class="fm-nav-section">
      <div class="fm-nav-section-label">个人收藏</div>
      <button
        class="fm-nav-item"
        :class="{ 'fm-nav-item-active': currentFolderId === 0 && !isRecycleBin }"
        type="button"
        @click="$emit('go-root')"
      >
        <Monitor class="fm-nav-icon" :size="15" :stroke-width="2" />
        <span class="fm-nav-label">桌面</span>
      </button>
    </div>

    <div class="fm-nav-section">
      <div class="fm-nav-section-label">位置</div>
      <button
        class="fm-nav-item"
        :class="{ 'fm-nav-item-active': isRecycleBin }"
        type="button"
        @click="$emit('open-recycle')"
      >
        <Trash2 class="fm-nav-icon" :size="15" :stroke-width="2" />
        <span class="fm-nav-label">回收站</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { Monitor, Trash2 } from 'lucide-vue-next'

defineProps<{
  currentFolderId: number
  isRecycleBin: boolean
}>()

defineEmits<{
  (e: 'go-root'): void
  (e: 'open-recycle'): void
}>()
</script>

<style scoped>
.fm-nav-pane {
  height: 100%;
  padding: 10px 8px 12px;
  background: transparent;
  box-sizing: border-box;
}

.fm-nav-section + .fm-nav-section {
  margin-top: 14px;
}

.fm-nav-section-label {
  margin: 0 8px 6px;
  color: var(--mac-app-text-secondary, rgba(60, 60, 67, 0.58));
  font: 600 11px/1.3 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  letter-spacing: 0.01em;
}

.fm-nav-item {
  width: 100%;
  height: 28px;
  margin-bottom: 1px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  color: var(--mac-app-text, rgba(20, 20, 22, 0.9));
  cursor: pointer;
  text-align: left;
  font: 400 12.5px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-nav-item:hover {
  background: color-mix(in srgb, var(--mac-app-text, #141416) 6%, transparent);
}

.fm-nav-item-active {
  background: var(--mac-app-selection, rgba(10, 132, 255, 0.16));
  color: color-mix(in srgb, var(--mac-app-accent, #0a84ff) 82%, #0b1b2d);
  font-weight: 600;
}

.fm-nav-icon {
  flex-shrink: 0;
  opacity: 0.92;
}

.fm-nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
