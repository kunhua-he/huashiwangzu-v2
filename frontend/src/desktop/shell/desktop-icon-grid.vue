<template>
  <div class="desktop-icon-grid">
    <div
      v-for="app in appList"
      :key="app.appKey"
      class="desktop-icon-item desktop-app-icon-item"
      :class="{ 'desktop-icon-item-selected': isSelected(`app:${app.appKey}`) }"
      :data-selection-key="`app:${app.appKey}`"
      @click="handleAppClick(app.appKey, $event)"
      @dblclick="$emit('openApp', app.appKey)"
      @contextmenu.prevent.stop="$emit('app-context-menu', app.appKey, $event)"
    >
      <div class="desktop-icon-image">
        <AppIcon :icon="app.icon" :size="54" />
      </div>
      <span class="desktop-icon-label">{{ app.appName }}</span>
    </div>
    <div
      v-for="file in fileList"
      :key="`file-${file.id}`"
      class="desktop-icon-item desktop-file-icon-item"
      :class="{
        'desktop-icon-item-selected': isSelected(`file:${file.id}`),
        'desktop-icon-item-drag-over': file.is_folder && currentDragOverId === `${file.id}`,
      }"
      :data-selection-key="`file:${file.id}`"
      :data-folder="file.is_folder ? '' : undefined"
      @mousedown="handleFileDragStart(file, $event)"
      @click="handleFileClick(file, $event)"
      @dblclick="$emit('openFile', file)"
    >
      <div class="desktop-icon-image">
        <FileVisualIcon :kind="file.is_folder || !file.format ? 'folder' : 'file'" :extension="file.format || ''" :size="48" />
      </div>
      <span class="desktop-icon-label">{{ getFileName(file) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import type { FileEntry } from '@/shared/api/types'
import AppIcon from '@/desktop/components/app-icon.vue'
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import { isSelected, select, appendSelection, clearSelection, selectedIds } from '@/desktop/selection/desktop-selection-state'
import { startDrag, dragState } from '@/desktop/drag-drop/drag-state'
import { getDropOverlayStyle, dropOverlay } from '@/desktop/drag-drop/drag-tool'
import { computed, onMounted } from 'vue'
import { formatFileDisplayName } from '@/shared/files/display-name'
import './desktop-icon-grid.css'

const currentDragOverId = computed(() => dragState.dragOverId ? `file:${dragState.dragOverId}` : null)

onMounted(() => {
  requestAnimationFrame(() => {
    document.querySelectorAll('[data-selection-key]').forEach(el => {
      const key = el.getAttribute('data-selection-key')
      if (key && dropOverlay[key]) {
        (el as HTMLElement).style.transform = getDropOverlayStyle(key)
      }
    })
  })
})

defineProps<{
  appList: AppRegistryEntry[]
  fileList?: FileEntry[]
}>()

defineEmits<{
  (e: 'openApp', appKey: string): void
  (e: 'openFile', file: FileEntry): void
  (e: 'app-context-menu', appKey: string, event: MouseEvent): void
}>()

function handleAppClick(appKey: string, e: MouseEvent) {
  const key = `app:${appKey}`
  if (e.ctrlKey) { appendSelection(key); return }
  if (isSelected(key)) return
  select(key)
}

function handleFileClick(file: FileEntry, e: MouseEvent) {
  const key = `file:${file.id}`
  if (e.ctrlKey) { appendSelection(key); return }
  if (isSelected(key)) return
  select(key)
}

function handleFileDragStart(file: FileEntry, e: MouseEvent) {
  if (e.button !== 0) return
  const key = `file:${file.id}`
  const selected = selectedIds.value
  const dragIds = selected.includes(key) ? selected : [key]
  if (!selected.includes(key)) {
    clearSelection()
    select(key)
  }
  startDrag(dragIds, e.clientX, e.clientY)
  e.stopPropagation()
}

function getFileName(file: FileEntry) {
  return file.is_folder ? String(file.file_name || '') : formatFileDisplayName(file.file_name, file.format)
}
</script>
