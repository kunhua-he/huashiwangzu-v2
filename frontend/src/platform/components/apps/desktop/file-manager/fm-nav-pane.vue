<template>
  <aside class="fm-nav-pane">
    <section class="fm-nav-section">
      <div class="fm-nav-section-label">个人收藏</div>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: currentKey === 'desktop' }"
        @click="$emit('go-root')"
      >
        <Monitor class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">桌面</span>
      </button>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: currentKey === 'documents' }"
        @click="$emit('open-named', 'documents')"
      >
        <FileText class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">文稿</span>
      </button>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: currentKey === 'downloads' }"
        @click="$emit('open-named', 'downloads')"
      >
        <Download class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">下载</span>
      </button>
    </section>

    <section class="fm-nav-section">
      <div class="fm-nav-section-label">位置</div>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: currentKey === 'recycle' }"
        @click="$emit('open-recycle')"
      >
        <Trash2 class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">回收站</span>
      </button>
      <button type="button" class="fm-nav-item" :class="{ active: currentKey === 'desktop' && !activeNamed }" @click="$emit('go-root')">
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
        class="fm-nav-item is-tag"
        disabled
        :title="`${tag.name}（标签筛选即将接入）`"
      >
        <span class="fm-tag-dot" :style="{ background: tag.color }" />
        <span class="fm-nav-label">{{ tag.name }}</span>
      </button>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Download, FileText, HardDrive, Monitor, Trash2 } from 'lucide-vue-next'

const props = defineProps<{
  currentFolderId: number
  isRecycleBin: boolean
  activeNamed?: 'documents' | 'downloads' | null
}>()

defineEmits<{
  (e: 'go-root'): void
  (e: 'open-recycle'): void
  (e: 'open-named', key: 'documents' | 'downloads'): void
}>()

const currentKey = computed(() => {
  if (props.isRecycleBin) return 'recycle'
  if (props.activeNamed === 'documents') return 'documents'
  if (props.activeNamed === 'downloads') return 'downloads'
  if (props.currentFolderId === 0) return 'desktop'
  return 'folder'
})

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
  height: calc(100% - 20px);
  margin: 10px 0 10px 10px;
  padding: 8px 0 12px;
  border-radius: 11px;
  box-sizing: border-box;
  overflow: auto;
  background: color-mix(in srgb, rgba(236, 236, 240, 0.72) 70%, rgba(255, 255, 255, 0.55));
  box-shadow:
    inset 0 0 0 0.5px rgba(255, 255, 255, 0.5),
    0 0 0 0.5px rgba(60, 60, 67, 0.08);
  backdrop-filter: blur(30px) saturate(170%);
  -webkit-backdrop-filter: blur(30px) saturate(170%);
}

.fm-nav-section + .fm-nav-section {
  margin-top: 14px;
}

.fm-nav-section-label {
  padding: 0 12px 4px;
  font: 600 11px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  color: rgba(60, 60, 67, 0.58);
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
  color: rgba(29, 29, 31, 0.92);
  text-align: left;
  cursor: pointer;
  font: 400 13px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-nav-item:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.05);
}

.fm-nav-item.active {
  background: rgba(10, 132, 255, 0.18);
}

.fm-nav-item.active .fm-nav-icon {
  color: var(--mac-app-accent, #0a84ff);
}

.fm-nav-item:disabled {
  opacity: 0.72;
  cursor: default;
}

/* Source list: monochrome SF-like glyphs, not filled app tiles */
.fm-nav-icon {
  flex-shrink: 0;
  color: rgba(60, 60, 67, 0.62);
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
  box-shadow: inset 0 0 0 0.5px rgba(0, 0, 0, 0.22);
  flex-shrink: 0;
}
</style>
