<template>
  <Teleport to="body">
    <div
      v-if="visible && item"
      class="fm-ql-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="快速查看"
      @click.self="$emit('close')"
      @keydown.esc.prevent="$emit('close')"
    >
      <section class="fm-ql-panel" tabindex="-1">
        <header class="fm-ql-head">
          <strong>{{ displayName(item) }}</strong>
          <button type="button" class="fm-ql-close" aria-label="关闭" @click="$emit('close')">×</button>
        </header>
        <div class="fm-ql-body">
          <FileVisualIcon
            :kind="item.is_folder || !item.format ? 'folder' : 'file'"
            :extension="item.format || ''"
            :size="128"
          />
          <div class="fm-ql-name">{{ displayName(item) }}</div>
          <div class="fm-ql-meta">
            {{ item.is_folder ? '文件夹' : ((item.format || '文件').toUpperCase()) }}
            <template v-if="!item.is_folder"> · {{ formatSize(item.file_size) }}</template>
          </div>
          <div class="fm-ql-hint">空格 关闭 · Enter 打开</div>
        </div>
        <footer class="fm-ql-foot">
          <button type="button" class="fm-ql-btn" @click="$emit('open', item)">打开</button>
          <button type="button" class="fm-ql-btn primary" @click="$emit('close')">完成</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import type { FileEntry } from '@/shared/api/types'

defineProps<{
  visible: boolean
  item: FileEntry | null
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

defineEmits<{
  (e: 'close'): void
  (e: 'open', item: FileEntry): void
}>()
</script>

<style scoped>
.fm-ql-overlay {
  position: fixed;
  inset: 0;
  z-index: 13000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
}

.fm-ql-panel {
  width: min(440px, 100%);
  border-radius: 14px;
  border: 0.5px solid rgba(60, 60, 67, 0.16);
  background: color-mix(in srgb, #f6f6f8 88%, white);
  box-shadow: 0 22px 56px rgba(0, 0, 0, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.55);
  overflow: hidden;
  color: #1d1d1f;
}

.fm-ql-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 40px;
  padding: 0 12px 0 16px;
  border-bottom: 0.5px solid rgba(60, 60, 67, 0.12);
  background: color-mix(in srgb, #f0f0f2 86%, white);
}

.fm-ql-head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font: 600 13px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-ql-close {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(60, 60, 67, 0.7);
  font-size: 18px;
  cursor: pointer;
}

.fm-ql-close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: #1d1d1f;
}

.fm-ql-body {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 28px 20px 18px;
}

.fm-ql-name {
  max-width: 100%;
  text-align: center;
  font: 600 15px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  word-break: break-word;
}

.fm-ql-meta,
.fm-ql-hint {
  color: rgba(60, 60, 67, 0.58);
  font-size: 12px;
}

.fm-ql-hint {
  font-size: 11px;
  opacity: 0.9;
}

.fm-ql-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 14px 14px;
  border-top: 0.5px solid rgba(60, 60, 67, 0.12);
  background: color-mix(in srgb, #f2f2f4 88%, white);
}

.fm-ql-btn {
  min-width: 72px;
  height: 28px;
  border: 0.5px solid rgba(60, 60, 67, 0.16);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  color: #1d1d1f;
  font: 500 12px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  cursor: pointer;
  padding: 0 12px;
}

.fm-ql-btn.primary {
  border-color: color-mix(in srgb, #0a84ff 70%, #0040dd);
  background: #0a84ff;
  color: #fff;
}
</style>
