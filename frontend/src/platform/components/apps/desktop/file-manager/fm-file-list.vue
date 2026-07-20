<template>
  <section class="fm-file-list" :class="`fm-view-${viewMode}`">
    <div v-if="viewMode === 'list'" class="fm-list-header" :style="listGridStyle">
      <span class="fm-col-icon"></span>
      <button class="fm-col-name" type="button" @click="$emit('sort', 'name')">
        名称
        <span v-if="sortColumn === 'name'" class="fm-sort-mark">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
      </button>
      <span class="fm-col-resizer" @mousedown.prevent.stop="startColumnResize('name', $event)" />
      <button class="fm-col-date" type="button" @click="$emit('sort', 'date')">
        修改日期
        <span v-if="sortColumn === 'date'" class="fm-sort-mark">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
      </button>
      <span class="fm-col-resizer" @mousedown.prevent.stop="startColumnResize('date', $event)" />
      <button class="fm-col-type" type="button" @click="$emit('sort', 'type')">
        种类
        <span v-if="sortColumn === 'type'" class="fm-sort-mark">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
      </button>
      <span class="fm-col-resizer" @mousedown.prevent.stop="startColumnResize('type', $event)" />
      <button class="fm-col-size" type="button" @click="$emit('sort', 'size')">
        大小
        <span v-if="sortColumn === 'size'" class="fm-sort-mark">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
      </button>
      <span class="fm-col-resizer" @mousedown.prevent.stop="startColumnResize('size', $event)" />
    </div>

    <LoadStateBanner
      v-if="loadStatus === 'stale'"
      class="fm-load-banner"
      :status="loadStatus"
      :error="loadError"
      stale-text="文件列表可能不是最新"
      @retry="emit('retry')"
    />

    <div v-if="loading && items.length === 0" class="fm-state">加载中...</div>

    <div v-else-if="loadStatus === 'error'" class="fm-state fm-state-error">
      <LoadStateBanner
        :status="loadStatus"
        :error="loadError"
        error-text="文件列表加载失败"
        @retry="emit('retry')"
      />
    </div>

    <MacEmptyState
      v-else-if="items.length === 0"
      class="fm-empty"
      title="这个文件夹是空的"
      description="把文件拖到这里，或从菜单新建。"
      icon="📁"
    />

    <template v-else>
      <FmGridView
        v-if="viewMode === 'grid'"
        :items="items"
        :icon-size="iconSize"
        :is-selected="isSelected"
        :is-drop-target="isDropTarget"
        :display-name="displayName"
        :item-tags="itemTags"
        :tag-color="tagColor"
        @entry-click="handleClick"
        @entry-dblclick="handleDoubleClick"
        @entry-mousedown="handleEntryMouseDown"
        @context-menu="(item, event) => emit('context-menu', item, event)"
      />

      <FmColumnView
        v-else-if="viewMode === 'column'"
        :columns="effectiveColumns"
        :preview-item="columnPreviewItem"
        :media="columnMedia"
        :is-drop-target="isDropTarget"
        :display-name="displayName"
        :format-size="formatSize"
        @column-click="handleColumnClick"
        @column-dblclick="handleColumnDoubleClick"
        @entry-mousedown="handleEntryMouseDown"
        @context-menu="(item, event) => emit('context-menu', item, event)"
      />

      <FmGalleryView
        v-else-if="viewMode === 'gallery'"
        :items="items"
        :selected="selected"
        :preview="galleryPreview"
        :strip-thumbs="stripThumbs"
        :is-selected="isSelected"
        :is-drop-target="isDropTarget"
        :display-name="displayName"
        :format-size="formatSize"
        @entry-click="handleClick"
        @entry-dblclick="handleDoubleClick"
        @entry-mousedown="handleEntryMouseDown"
        @context-menu="(item, event) => emit('context-menu', item, event)"
      />

      <FmListView
        v-else
        :items="items"
        :list-grid-style="listGridStyle"
        :is-selected="isSelected"
        :is-drop-target="isDropTarget"
        :display-name="displayName"
        :format-size="formatSize"
        :item-tags="itemTags"
        :tag-color="tagColor"
        :renaming-id="renamingId"
        :rename-draft="renameDraft"
        @entry-click="handleClick"
        @entry-dblclick="handleDoubleClick"
        @entry-mousedown="handleEntryMouseDown"
        @context-menu="(item, event) => emit('context-menu', item, event)"
        @maybe-rename="maybeStartInlineRename"
        @update:rename-draft="renameDraft = $event"
        @commit-rename="commitInlineRename"
        @cancel-rename="cancelInlineRename"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import type { FileEntry } from '@/shared/api/types'
import LoadStateBanner from '@/shared/components/load-state-banner.vue'
import { MacEmptyState } from '@/desktop/app-kit'
import { FINDER_TAGS } from './finder-tags'
import type { ApiErrorInfo } from '@/shared/api/response-transform'
import type { LoadStatus } from '@/shared/composables/use-load-state'
import { useFmPreviewMedia } from './use-fm-preview-media'
import { useFmEntryInteraction } from './use-fm-entry-interaction'
import { useFmInlineRename } from './use-fm-inline-rename'
import { useFmListColumnResize } from './use-fm-list-column-resize'
import type { ColumnStackItem, ListColumnWidths } from './fm-file-list-types'
import FmGridView from './fm-grid-view.vue'
import FmListView from './fm-list-view.vue'
import FmColumnView from './fm-column-view.vue'
import FmGalleryView from './fm-gallery-view.vue'
import './fm-file-list.css'

export type { ColumnStackItem, ListColumnWidths } from './fm-file-list-types'

const props = withDefaults(defineProps<{
  items: FileEntry[]
  selectedId: number | null
  selectedIds?: number[]
  viewMode: 'grid' | 'list' | 'column' | 'gallery'
  iconSize?: number
  columnStack?: ColumnStackItem[]
  columnWidths?: ListColumnWidths
  loading: boolean
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
  tagsOf?: (file: FileEntry) => string[]
  tagRevision?: number
  sortColumn: 'name' | 'date' | 'type' | 'size'
  sortDirection: 'asc' | 'desc'
  loadStatus: LoadStatus
  loadError: ApiErrorInfo | null
}>(), {
  iconSize: 50,
  columnStack: () => [],
  columnWidths: () => ({ name: 220, date: 132, type: 88, size: 72 }),
  selectedIds: () => [],
  tagsOf: () => [],
  tagRevision: 0,
})

const emit = defineEmits<{
  (e: 'select', item: FileEntry, opts?: { additive?: boolean; range?: boolean }): void
  (e: 'open', item: FileEntry): void
  (e: 'context-menu', item: FileEntry, event: MouseEvent): void
  (e: 'sort', column: string): void
  (e: 'update:columnWidths', value: Required<ListColumnWidths>): void
  (e: 'rename-inline', item: FileEntry, nextName: string): void
  (e: 'retry'): void
  (e: 'column-select', item: FileEntry, columnIndex: number): void
  (e: 'column-open', item: FileEntry, columnIndex: number): void
}>()

function isSelected(id: number) {
  if (props.selectedIds?.length) return props.selectedIds.includes(id)
  return props.selectedId === id
}

function itemTags(item: FileEntry) {
  void props.tagRevision
  return props.tagsOf ? props.tagsOf(item) : []
}

function tagColor(tag: string) {
  return FINDER_TAGS.find((t) => t.key === tag)?.color || 'rgb(152,152,157)'
}

const selected = computed(() => props.items.find((item) => item.id === props.selectedId) || null)

const effectiveColumns = computed<ColumnStackItem[]>(() => {
  if (props.columnStack?.length) return props.columnStack
  return [{
    folderId: 0,
    name: '当前',
    items: props.items,
    selectedId: props.selectedId,
  }]
})

const columnPreviewItem = computed(() => {
  const cols = effectiveColumns.value
  for (let i = cols.length - 1; i >= 0; i -= 1) {
    const col = cols[i]
    if (col.selectedId == null) continue
    const hit = col.items.find((item) => item.id === col.selectedId)
    if (hit) return hit
  }
  return selected.value
})

const { galleryPreview, columnMedia, stripThumbs } = useFmPreviewMedia({
  viewMode: toRef(props, 'viewMode'),
  selected,
  items: toRef(props, 'items'),
  columnPreviewItem,
})

const {
  handleEntryMouseDown,
  handleClick,
  handleDoubleClick,
  handleColumnClick,
  handleColumnDoubleClick,
  isDropTarget,
} = useFmEntryInteraction({
  getItems: () => props.items,
  getSelectedIds: () => props.selectedIds || [],
  onSelect: (item, opts) => emit('select', item, opts),
  onOpen: (item) => emit('open', item),
  onColumnSelect: (item, columnIndex) => emit('column-select', item, columnIndex),
  onColumnOpen: (item, columnIndex) => emit('column-open', item, columnIndex),
})

const {
  renamingId,
  renameDraft,
  maybeStartInlineRename,
  cancelInlineRename,
  commitInlineRename,
} = useFmInlineRename({
  isSelected,
  onRename: (item, nextName) => emit('rename-inline', item, nextName),
})

const { listGridStyle, startColumnResize } = useFmListColumnResize({
  columnWidths: toRef(props, 'columnWidths'),
  onUpdate: (value) => emit('update:columnWidths', value),
})
</script>
