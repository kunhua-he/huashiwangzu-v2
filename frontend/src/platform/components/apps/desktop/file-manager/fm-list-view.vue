<template>
  <div class="fm-content-list">
    <button
      v-for="item in items"
      :key="`${item.is_folder ? 'folder' : 'file'}-${item.id}`"
      :draggable="false"
      class="fm-entry"
      :style="listGridStyle"
      :data-selection-key="(item.is_folder ? 'folder' : 'file') + ':' + item.id"
      :data-folder="item.is_folder ? String(item.id) : undefined"
      :class="{ 'fm-entry-selected': isSelected(item.id), 'fm-entry-drop': isDropTarget(item) }"
      type="button"
      @click="onClick(item, $event)"
      @dblclick="onDoubleClick(item, $event)"
      @contextmenu.prevent.stop="$emit('context-menu', item, $event)"
      @mousedown.stop="onMouseDown(item, $event)"
    >
      <FileVisualIcon
        :kind="item.is_folder || !item.format ? 'folder' : 'file'"
        :extension="item.format || ''"
        :size="18"
      />
      <span class="fm-entry-name" @click.stop="onMaybeRename(item, $event)">
        <input
          v-if="renamingId === item.id"
          class="fm-inline-rename"
          :value="renameDraft"
          @mousedown.stop
          @click.stop
          @input="onRenameInput"
          @keydown.enter.prevent="onCommitRename(item)"
          @keydown.esc.prevent="onCancelRename"
          @blur="onCommitRename(item)"
        >
        <template v-else>
          {{ displayName(item) }}
          <span v-if="itemTags(item).length" class="fm-entry-tags inline">
            <i
              v-for="tag in itemTags(item)"
              :key="tag"
              class="fm-entry-tag-dot"
              :style="{ background: tagColor(tag) }"
            />
          </span>
        </template>
      </span>
      <span class="fm-entry-spacer" aria-hidden="true" />
      <span class="fm-entry-date">{{ formatListDate(item.updated_at || item.created_at) }}</span>
      <span class="fm-entry-spacer" aria-hidden="true" />
      <span class="fm-entry-kind">{{ item.is_folder ? '文件夹' : kindLabel(item) }}</span>
      <span class="fm-entry-spacer" aria-hidden="true" />
      <span class="fm-entry-size">{{ item.is_folder ? '—' : formatSize(item.file_size) }}</span>
      <span class="fm-entry-spacer" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup lang="ts">
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import type { FileEntry } from '@/shared/api/types'
import type { CSSProperties } from 'vue'

defineProps<{
  items: FileEntry[]
  listGridStyle: CSSProperties
  isSelected: (id: number) => boolean
  isDropTarget: (item: FileEntry) => boolean
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
  itemTags: (file: FileEntry) => string[]
  tagColor: (tag: string) => string
  renamingId: number | null
  renameDraft: string
}>()

const emit = defineEmits<{
  (e: 'entry-click', item: FileEntry, event: MouseEvent): void
  (e: 'entry-dblclick', item: FileEntry, event: MouseEvent): void
  (e: 'entry-mousedown', item: FileEntry, event: MouseEvent): void
  (e: 'context-menu', item: FileEntry, event: MouseEvent): void
  (e: 'maybe-rename', item: FileEntry, event: MouseEvent): void
  (e: 'update:renameDraft', value: string): void
  (e: 'commit-rename', item: FileEntry): void
  (e: 'cancel-rename'): void
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
function onMaybeRename(item: FileEntry, event: MouseEvent) {
  emit('maybe-rename', item, event)
}
function onRenameInput(event: Event) {
  emit('update:renameDraft', (event.target as HTMLInputElement).value)
}
function onCommitRename(item: FileEntry) {
  emit('commit-rename', item)
}
function onCancelRename() {
  emit('cancel-rename')
}

function kindLabel(item: FileEntry) {
  if (item.is_folder) return '文件夹'
  const ext = String(item.format || '').toLowerCase()
  if (!ext) return '文件'
  const map: Record<string, string> = {
    pdf: 'PDF 文稿',
    png: 'PNG 图像',
    jpg: 'JPEG 图像',
    jpeg: 'JPEG 图像',
    gif: 'GIF 图像',
    webp: 'WebP 图像',
    svg: 'SVG 图像',
    txt: '纯文本',
    md: 'Markdown',
    json: 'JSON',
    csv: 'CSV',
    zip: 'ZIP 归档',
    mp4: 'MPEG-4 影片',
    mov: 'QuickTime 影片',
    mp3: 'MP3 音频',
    wav: 'WAV 音频',
    doc: 'Word 文稿',
    docx: 'Word 文稿',
    xls: 'Excel 表格',
    xlsx: 'Excel 表格',
    ppt: 'PowerPoint',
    pptx: 'PowerPoint',
    js: 'JavaScript',
    ts: 'TypeScript',
    vue: 'Vue 源码',
    py: 'Python 源码',
    php: 'PHP 源码',
  }
  return map[ext] || `${ext.toUpperCase()} 文件`
}

function formatListDate(raw?: string | null) {
  if (!raw) return ''
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw).slice(0, 16)
  const now = new Date()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (d.toDateString() === now.toDateString()) return `今天 ${time}`
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
</script>
