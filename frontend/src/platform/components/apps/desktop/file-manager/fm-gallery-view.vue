<template>
  <div class="fm-content-gallery">
    <div class="fm-gallery-stage">
      <template v-if="selected">
        <div v-if="preview.loading" class="fm-gallery-state">加载预览…</div>
        <img
          v-else-if="preview.mode === 'image' && preview.objectUrl"
          class="fm-gallery-media"
          :src="preview.objectUrl"
          :alt="displayName(selected)"
        >
        <iframe
          v-else-if="preview.mode === 'pdf' && preview.objectUrl"
          class="fm-gallery-pdf"
          :src="preview.objectUrl"
          title="PDF 预览"
        />
        <pre v-else-if="preview.mode === 'text'" class="fm-gallery-text">{{ preview.text }}</pre>
        <template v-else>
          <FileVisualIcon
            :kind="selected.is_folder || !selected.format ? 'folder' : 'file'"
            :extension="selected.format || ''"
            :size="148"
          />
        </template>
        <div class="fm-gallery-name">{{ displayName(selected) }}</div>
        <div class="fm-gallery-meta">
          {{ selected.is_folder ? '文件夹' : ((selected.format || '文件').toUpperCase()) }}
          <template v-if="!selected.is_folder"> · {{ formatSize(selected.file_size) }}</template>
          <template v-if="preview.truncated"> · 已截断</template>
        </div>
      </template>
      <div v-else class="fm-gallery-empty">选择一个项目以在画廊中预览</div>
    </div>
    <div class="fm-gallery-strip">
      <button
        v-for="item in items"
        :key="`g-${item.is_folder ? 'folder' : 'file'}-${item.id}`"
        type="button"
        class="fm-gallery-thumb"
        :class="{ 'fm-entry-selected': isSelected(item.id), 'fm-entry-drop': isDropTarget(item) }"
        :data-selection-key="(item.is_folder ? 'folder' : 'file') + ':' + item.id"
        @click="onClick(item, $event)"
        @dblclick="onDoubleClick(item, $event)"
        @contextmenu.prevent.stop="$emit('context-menu', item, $event)"
        @mousedown.stop="onMouseDown(item, $event)"
      >
        <img
          v-if="stripThumbs[item.id]"
          class="fm-gallery-strip-img"
          :src="stripThumbs[item.id]"
          :alt="displayName(item)"
        >
        <FileVisualIcon
          v-else
          :kind="item.is_folder || !item.format ? 'folder' : 'file'"
          :extension="item.format || ''"
          :size="42"
        />
        <span class="fm-gallery-thumb-name">{{ displayName(item) }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import type { FileEntry } from '@/shared/api/types'
import type { FmPreviewMediaState } from './use-fm-preview-media'

defineProps<{
  items: FileEntry[]
  selected: FileEntry | null
  preview: FmPreviewMediaState
  stripThumbs: Record<number, string>
  isSelected: (id: number) => boolean
  isDropTarget: (item: FileEntry) => boolean
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

const emit = defineEmits<{
  (e: 'entry-click', item: FileEntry, event: MouseEvent): void
  (e: 'entry-dblclick', item: FileEntry, event: MouseEvent): void
  (e: 'entry-mousedown', item: FileEntry, event: MouseEvent): void
  (e: 'context-menu', item: FileEntry, event: MouseEvent): void
}>()

function onClick(item: FileEntry, event: MouseEvent) {
  emit('entry-click', item, event)
}
function onDoubleClick(item: FileEntry, event: MouseEvent) {
  emit('entry-dblclick', item, event)
}
function onMouseDown(item: FileEntry, event: MouseEvent) {
  emit('entry-mousedown', item, event)
}
</script>
