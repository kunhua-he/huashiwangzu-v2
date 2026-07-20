<template>
  <div class="fm-content-column">
    <div
      v-for="(col, colIndex) in columns"
      :key="`col-${col.folderId}-${colIndex}`"
      class="fm-column-pane"
    >
      <button
        v-for="item in col.items"
        :key="`${item.is_folder ? 'folder' : 'file'}-${item.id}`"
        :draggable="false"
        class="fm-column-row"
        :data-selection-key="(item.is_folder ? 'folder' : 'file') + ':' + item.id"
        :data-folder="item.is_folder ? String(item.id) : undefined"
        :class="{ 'fm-entry-selected': col.selectedId === item.id, 'fm-entry-drop': isDropTarget(item) }"
        type="button"
        @click="onColumnClick(item, colIndex, $event)"
        @dblclick="onColumnDoubleClick(item, colIndex, $event)"
        @contextmenu.prevent.stop="$emit('context-menu', item, $event)"
        @mousedown.stop="onMouseDown(item, $event)"
      >
        <FileVisualIcon
          :kind="item.is_folder || !item.format ? 'folder' : 'file'"
          :extension="item.format || ''"
          :size="18"
        />
        <span class="fm-entry-name">{{ displayName(item) }}</span>
        <span v-if="item.is_folder" class="fm-column-chevron" aria-hidden="true">›</span>
      </button>
      <div v-if="!col.items.length" class="fm-column-empty">空文件夹</div>
    </div>
    <div class="fm-column-preview">
      <template v-if="previewItem">
        <div v-if="media.loading" class="fm-column-preview-empty">加载预览…</div>
        <img
          v-else-if="media.mode === 'image' && media.objectUrl"
          class="fm-column-preview-media"
          :src="media.objectUrl"
          :alt="displayName(previewItem)"
        >
        <iframe
          v-else-if="media.mode === 'pdf' && media.objectUrl"
          class="fm-column-preview-pdf"
          :src="media.objectUrl"
          title="PDF 预览"
        />
        <pre v-else-if="media.mode === 'text'" class="fm-column-preview-text">{{ media.text }}</pre>
        <FileVisualIcon
          v-else
          :kind="previewItem.is_folder || !previewItem.format ? 'folder' : 'file'"
          :extension="previewItem.format || ''"
          :size="72"
        />
        <div class="fm-column-preview-name">{{ displayName(previewItem) }}</div>
        <div class="fm-column-preview-meta">
          {{ previewItem.is_folder ? '文件夹' : (previewItem.format || '文件') }}
          <template v-if="!previewItem.is_folder"> · {{ formatSize(previewItem.file_size) }}</template>
        </div>
      </template>
      <div v-else class="fm-column-preview-empty">选择一个项目以预览</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import type { FileEntry } from '@/shared/api/types'
import type { ColumnStackItem } from './fm-file-list-types'
import type { FmPreviewMediaState } from './use-fm-preview-media'

defineProps<{
  columns: ColumnStackItem[]
  previewItem: FileEntry | null
  media: FmPreviewMediaState
  isDropTarget: (item: FileEntry) => boolean
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

const emit = defineEmits<{
  (e: 'column-click', item: FileEntry, columnIndex: number, event: MouseEvent): void
  (e: 'column-dblclick', item: FileEntry, columnIndex: number, event: MouseEvent): void
  (e: 'entry-mousedown', item: FileEntry, event: MouseEvent): void
  (e: 'context-menu', item: FileEntry, event: MouseEvent): void
}>()

function onColumnClick(item: FileEntry, columnIndex: number, event: MouseEvent) {
  emit('column-click', item, columnIndex, event)
}
function onColumnDoubleClick(item: FileEntry, columnIndex: number, event: MouseEvent) {
  emit('column-dblclick', item, columnIndex, event)
}
function onMouseDown(item: FileEntry, event: MouseEvent) {
  emit('entry-mousedown', item, event)
}
</script>
