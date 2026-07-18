<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fm-prop-overlay"
      role="presentation"
      @click.self="close"
    >
      <section
        class="fm-prop-panel"
        role="dialog"
        aria-modal="true"
        :aria-label="item ? displayName(item) : '属性'"
      >
        <header class="fm-prop-head">
          <div class="fm-prop-title-wrap">
            <strong>{{ item ? displayName(item) : '属性' }}</strong>
            <span>{{ item ? (item.is_folder ? '文件夹' : '文件') : '未选择项目' }}</span>
          </div>
          <button type="button" class="fm-prop-close" aria-label="关闭" @click="close">×</button>
        </header>

        <div v-if="item" class="fm-prop-body">
          <div class="fm-prop-row">
            <span class="fm-prop-label">名称</span>
            <span class="fm-prop-value">{{ displayName(item) }}</span>
          </div>
          <div class="fm-prop-row">
            <span class="fm-prop-label">类型</span>
            <span class="fm-prop-value">{{ item.is_folder ? '文件夹' : (item.format?.toUpperCase() || '文件') }}</span>
          </div>
          <div class="fm-prop-row">
            <span class="fm-prop-label">大小</span>
            <span class="fm-prop-value">{{ item.is_folder ? '—' : formatSize(item.file_size) }}</span>
          </div>
          <div class="fm-prop-row">
            <span class="fm-prop-label">创建时间</span>
            <span class="fm-prop-value">{{ item.created_at || '—' }}</span>
          </div>
        </div>
        <div v-else class="fm-prop-empty">请选择一个文件或文件夹</div>

        <footer class="fm-prop-foot">
          <button type="button" class="fm-prop-btn" @click="close">完成</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { FileEntry } from '@/shared/api/types'

defineProps<{
  visible: boolean
  item: FileEntry | null
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()

function close() {
  emit('update:visible', false)
}
</script>

<style scoped>
.fm-prop-overlay {
  position: fixed;
  inset: 0;
  z-index: 12000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(8px) saturate(140%);
  -webkit-backdrop-filter: blur(8px) saturate(140%);
}

.fm-prop-panel {
  width: min(420px, 100%);
  border: 1px solid var(--mac-app-border, rgba(60, 60, 67, 0.14));
  border-radius: 14px;
  background: color-mix(in srgb, var(--mac-app-surface, #f6f6f8) 88%, white);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.55);
  overflow: hidden;
  color: var(--mac-app-text, #1d1d1f);
}

.fm-prop-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--mac-app-border, rgba(60, 60, 67, 0.12));
  background: var(--mac-app-surface-toolbar, rgba(246, 246, 250, 0.9));
}

.fm-prop-title-wrap {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.fm-prop-title-wrap strong {
  font: var(--mac-app-font-title, 600 13px/1.3 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-prop-title-wrap span {
  font: var(--mac-app-font-caption, 400 11px/1.3 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif);
  color: var(--mac-app-text-secondary, #6e6e73);
}

.fm-prop-close {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--mac-app-text-secondary, #6e6e73);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.fm-prop-close:hover {
  background: color-mix(in srgb, var(--mac-app-text, #1d1d1f) 8%, transparent);
  color: var(--mac-app-text, #1d1d1f);
}

.fm-prop-body {
  padding: 8px 16px 4px;
}

.fm-prop-row {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--mac-app-border, rgba(60, 60, 67, 0.12)) 80%, transparent);
}

.fm-prop-row:last-child {
  border-bottom: 0;
}

.fm-prop-label {
  font-size: 12px;
  color: var(--mac-app-text-secondary, #6e6e73);
}

.fm-prop-value {
  font-size: 12px;
  color: var(--mac-app-text, #1d1d1f);
  word-break: break-word;
}

.fm-prop-empty {
  padding: 28px 16px;
  text-align: center;
  color: var(--mac-app-text-secondary, #8e8e93);
  font-size: 12px;
}

.fm-prop-foot {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px 14px;
  border-top: 1px solid var(--mac-app-border, rgba(60, 60, 67, 0.12));
  background: color-mix(in srgb, var(--mac-app-surface-status, #f3f4f6) 70%, white);
}

.fm-prop-btn {
  min-width: 72px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  padding: 0 14px;
  background: var(--mac-app-accent, #0a84ff);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.fm-prop-btn:hover {
  filter: brightness(0.97);
}
</style>
