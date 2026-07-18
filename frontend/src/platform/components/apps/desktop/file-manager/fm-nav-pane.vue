<template>
  <aside class="fm-nav-pane">
    <section class="fm-nav-section">
      <div class="fm-nav-section-label">个人收藏</div>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: currentFolderId === 0 && !isRecycleBin }"
        @click="$emit('go-root')"
      >
        <Monitor class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">桌面</span>
      </button>
      <button type="button" class="fm-nav-item is-muted" disabled title="即将接入">
        <Clock class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">最近使用</span>
      </button>
      <button type="button" class="fm-nav-item is-muted" disabled title="即将接入">
        <FileText class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">文稿</span>
      </button>
      <button type="button" class="fm-nav-item is-muted" disabled title="即将接入">
        <Download class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">下载</span>
      </button>
    </section>

    <section class="fm-nav-section">
      <div class="fm-nav-section-label">位置</div>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: isRecycleBin }"
        @click="$emit('open-recycle')"
      >
        <Trash2 class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">回收站</span>
      </button>
      <button type="button" class="fm-nav-item is-muted" disabled title="即将接入">
        <HardDrive class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">本机</span>
      </button>
    </section>

    <section class="fm-nav-section">
      <div class="fm-nav-section-label">标签</div>
      <button
        v-for="tag in tags"
        :key="tag.name"
        type="button"
        class="fm-nav-item is-muted"
        disabled
        :title="`${tag.name}（即将接入）`"
      >
        <span class="fm-tag-dot" :style="{ background: tag.color }" />
        <span class="fm-nav-label">{{ tag.name }}</span>
      </button>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { Clock, Download, FileText, HardDrive, Monitor, Trash2 } from 'lucide-vue-next'

defineProps<{
  currentFolderId: number
  isRecycleBin: boolean
}>()

defineEmits<{
  (e: 'go-root'): void
  (e: 'open-recycle'): void
}>()

const tags = [
  { name: '红色', color: 'rgb(255, 69, 58)' },
  { name: '橙色', color: 'rgb(255, 159, 10)' },
  { name: '黄色', color: 'rgb(255, 214, 10)' },
  { name: '绿色', color: 'rgb(48, 209, 88)' },
  { name: '蓝色', color: 'rgb(10, 132, 255)' },
  { name: '紫色', color: 'rgb(191, 90, 242)' },
  { name: '灰色', color: 'rgb(152, 152, 157)' },
]
</script>

<style scoped>
.fm-nav-pane {
  height: 100%;
  margin: 10px 0 10px 10px;
  padding: 8px 0 10px;
  border-radius: 12px;
  box-sizing: border-box;
  overflow: auto;
  background: color-mix(in srgb, rgba(246, 246, 248, 0.72) 78%, white);
  box-shadow:
    inset 0 0 0 0.5px rgba(255, 255, 255, 0.45),
    0 0 0 0.5px rgba(60, 60, 67, 0.08);
  backdrop-filter: blur(28px) saturate(165%);
  -webkit-backdrop-filter: blur(28px) saturate(165%);
}

.fm-nav-section + .fm-nav-section {
  margin-top: 12px;
}

.fm-nav-section-label {
  padding: 0 12px 3px;
  font: 600 11px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  color: var(--mac-app-text-secondary, rgba(60, 60, 67, 0.62));
}

.fm-nav-item {
  width: calc(100% - 8px);
  height: 28px;
  margin: 0 4px 1px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--mac-app-text, #1d1d1f);
  text-align: left;
  cursor: pointer;
  font: 400 13px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  transition: background 100ms ease, color 100ms ease;
}

.fm-nav-item:hover:not(:disabled) {
  background: color-mix(in srgb, var(--mac-app-text, #1d1d1f) 6%, transparent);
}

.fm-nav-item.active {
  background: var(--mac-app-selection, rgba(10, 132, 255, 0.16));
}

.fm-nav-item.active .fm-nav-icon {
  color: var(--mac-app-accent, #0a84ff);
}

.fm-nav-item.is-muted {
  opacity: 0.55;
  cursor: default;
}

.fm-nav-icon {
  flex-shrink: 0;
  color: var(--mac-app-text-secondary, #6e6e73);
}

.fm-nav-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-tag-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  flex-shrink: 0;
  box-shadow: inset 0 0 0 0.5px rgba(0, 0, 0, 0.25);
}
</style>
