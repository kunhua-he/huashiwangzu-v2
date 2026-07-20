<template>
  <div class="fm-content-grid" :style="gridStyle">
    <button
      v-for="item in items"
      :key="`${item.is_folder ? 'folder' : 'file'}-${item.id}`"
      :draggable="false"
      class="fm-entry"
      :data-selection-key="(item.is_folder ? 'folder' : 'file') + ':' + item.id"
      :data-folder="item.is_folder ? String(item.id) : undefined"
      :class="{ 'fm-entry-selected': isSelected(item.id), 'fm-entry-drop': isDropTarget(item) }"
      type="button"
      @click="onClick(item, $event)"
      @dblclick="onDoubleClick(item, $event)"
      @contextmenu.prevent.stop="$emit('context-menu', item, $event)"
      @mousedown.stop="onMouseDown(item, $event)"
    >
      <span class="fm-entry-icon-wrap" :style="iconWrapStyle">
        <FileVisualIcon
          :kind="item.is_folder || !item.format ? 'folder' : 'file'"
          :extension="item.format || ''"
          :size="gridIconSize"
        />
      </span>
      <span class="fm-entry-name" :style="nameStyle">{{ displayName(item) }}</span>
      <span v-if="itemTags(item).length" class="fm-entry-tags">
        <i
          v-for="tag in itemTags(item)"
          :key="tag"
          class="fm-entry-tag-dot"
          :style="{ background: tagColor(tag) }"
        />
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import type { FileEntry } from '@/shared/api/types'

const props = withDefaults(defineProps<{
  items: FileEntry[]
  iconSize?: number
  isSelected: (id: number) => boolean
  isDropTarget: (item: FileEntry) => boolean
  displayName: (file: FileEntry) => string
  itemTags: (file: FileEntry) => string[]
  tagColor: (tag: string) => string
}>(), {
  iconSize: 50,
})

const emit = defineEmits<{
  (e: 'entry-click', item: FileEntry, event: MouseEvent): void
  (e: 'entry-dblclick', item: FileEntry, event: MouseEvent): void
  (e: 'entry-mousedown', item: FileEntry, event: MouseEvent): void
  (e: 'context-menu', item: FileEntry, event: MouseEvent): void
}>()

const gridIconSize = computed(() => Math.max(28, Math.round((props.iconSize || 50) * 0.78)))
const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(auto-fill, minmax(${Math.max(80, (props.iconSize || 50) + 30)}px, 1fr))`,
  gap: '10px',
}))
const iconWrapStyle = computed(() => ({
  width: `${Math.round((props.iconSize || 50) * 1.28)}px`,
  height: `${Math.round((props.iconSize || 50) * 1.09)}px`,
}))
const nameStyle = computed(() => ({
  maxWidth: `${Math.max(76, (props.iconSize || 50) + 26)}px`,
}))

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
