<template>
  <Teleport to="body">
    <Transition name="preview-fade">
      <div
        v-if="visible"
        class="taskbar-preview"
        :style="previewPosition"
        @mouseenter="onPreviewEnter"
        @mouseleave="onPreviewLeave"
      >
        <div class="preview-header">
          <span class="preview-title">{{ windowTitle }}</span>
          <button class="preview-close" @click="$emit('closeWindow', windowId)" title="关闭窗口">✕</button>
        </div>
        <div class="preview-body">
          <div class="preview-icon-display">
            <AppIcon :icon="windowIcon" :size="48" />
          </div>
          <div class="preview-label">{{ windowTitle }}</div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '@/desktop/components/app-icon.vue'

const props = defineProps<{
  visible: boolean
  windowId: string
  windowTitle: string
  windowIcon: string
  anchorRect: { x: number; y: number; width: number; height: number } | null
}>()

const emit = defineEmits<{
  (e: 'closeWindow', id: string): void
  (e: 'keepAlive'): void
  (e: 'dismiss'): void
}>()

const previewPosition = computed(() => {
  if (!props.anchorRect) return { display: 'none' }
  const x = props.anchorRect.x + props.anchorRect.width / 2 - 100
  const y = props.anchorRect.y - 152
  return {
    left: `${Math.max(4, x)}px`,
    top: `${Math.max(4, y)}px`,
  }
})

function onPreviewEnter() {
  emit('keepAlive')
}

function onPreviewLeave() {
  emit('dismiss')
}
</script>

<style scoped>
.taskbar-preview {
  position: fixed;
  width: 200px;
  height: 140px;
  background: rgba(15, 23, 42, 0.82);
  backdrop-filter: blur(16px) saturate(1.2);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2);
  z-index: 10100;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.preview-title {
  font-size: 11px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
.preview-close {
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}
.preview-close:hover {
  background: rgba(239, 68, 68, 0.8);
  color: #fff;
}
.preview-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
}
.preview-icon-display {
  opacity: 0.9;
}
.preview-label {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.preview-fade-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.preview-fade-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.preview-fade-enter-from,
.preview-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
