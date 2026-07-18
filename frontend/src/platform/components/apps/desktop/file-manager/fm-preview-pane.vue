<template>
  <aside class="fm-preview-pane" aria-label="预览">
    <template v-if="item">
      <div class="fm-preview-visual">
        <img
          v-if="thumbUrl"
          class="fm-preview-thumb"
          :src="thumbUrl"
          :alt="displayName(item)"
        >
        <FileVisualIcon
          v-else
          :kind="item.is_folder || !item.format ? 'folder' : 'file'"
          :extension="item.format || ''"
          :size="88"
        />
      </div>
      <div class="fm-preview-name">{{ displayName(item) }}</div>
      <div class="fm-preview-kind">
        {{ item.is_folder ? '文件夹' : ((item.format || '文件').toUpperCase()) }}
      </div>

      <dl class="fm-preview-meta">
        <div class="fm-preview-row">
          <dt>大小</dt>
          <dd>{{ item.is_folder ? '—' : formatSize(item.file_size) }}</dd>
        </div>
        <div class="fm-preview-row">
          <dt>修改</dt>
          <dd>{{ formatDate(item.updated_at || item.created_at) }}</dd>
        </div>
        <div v-if="item.updated_at && item.created_at && item.updated_at !== item.created_at" class="fm-preview-row">
          <dt>创建</dt>
          <dd>{{ formatDate(item.created_at) }}</dd>
        </div>
        <div v-if="!item.is_folder && item.format" class="fm-preview-row">
          <dt>种类</dt>
          <dd>{{ item.format.toUpperCase() }} 文档</dd>
        </div>
      </dl>
    </template>
    <div v-else class="fm-preview-empty">
      <span>未选择项目</span>
      <small>选择文件或文件夹以查看信息</small>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import { fetchDownloadBlob, fetchFilePreview, fetchBlobByApiPath } from '@/shared/api/desktop'
import type { FileEntry } from '@/shared/api/types'

const props = defineProps<{
  item: FileEntry | null
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

const thumbUrl = ref('')
let loadToken = 0

const IMAGE_EXTS = new Set([
  'jpg', 'jpeg', 'jpe', 'jfif', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tif', 'tiff', 'avif',
])

function revokeThumb() {
  if (thumbUrl.value) {
    URL.revokeObjectURL(thumbUrl.value)
    thumbUrl.value = ''
  }
}

function extOf(item: FileEntry) {
  return String(item.format || '').toLowerCase().replace(/^\./, '')
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

async function loadThumb(item: FileEntry) {
  const token = ++loadToken
  revokeThumb()
  if (item.is_folder) return
  const ext = extOf(item)
  if (!IMAGE_EXTS.has(ext)) return
  try {
    const data = await fetchFilePreview(item.id)
    if (token !== loadToken) return
    const downloadUrl = asString((data as Record<string, unknown>).download_url)
    let blob: Blob
    if (downloadUrl) {
      try {
        blob = await fetchBlobByApiPath(downloadUrl)
      } catch {
        blob = await fetchDownloadBlob(item.id, 'standard-image').catch(() => fetchDownloadBlob(item.id))
      }
    } else {
      blob = await fetchDownloadBlob(item.id, 'standard-image').catch(() => fetchDownloadBlob(item.id))
    }
    if (token !== loadToken) return
    thumbUrl.value = URL.createObjectURL(blob)
  } catch {
    // keep icon fallback
  }
}

watch(
  () => [props.item?.id, props.item?.format, props.item?.is_folder] as const,
  () => {
    if (!props.item) {
      loadToken += 1
      revokeThumb()
      return
    }
    void loadThumb(props.item)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  loadToken += 1
  revokeThumb()
})

function formatDate(raw?: string | null) {
  if (!raw) return '—'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw).slice(0, 16)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (sameDay) return `今天 ${time}`
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.fm-preview-pane {
  width: 220px;
  flex-shrink: 0;
  border-left: 0.5px solid rgba(60, 60, 67, 0.14);
  background: color-mix(in srgb, #f7f7f9 92%, white);
  padding: 20px 16px;
  box-sizing: border-box;
  overflow: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.fm-preview-visual {
  width: 140px;
  height: 110px;
  display: grid;
  place-items: center;
  margin-bottom: 12px;
}

.fm-preview-thumb {
  max-width: 140px;
  max-height: 110px;
  border-radius: 8px;
  object-fit: contain;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  background: #fff;
}

.fm-preview-name {
  width: 100%;
  text-align: center;
  font: 600 13px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  color: #1d1d1f;
  word-break: break-word;
  margin-bottom: 4px;
}

.fm-preview-kind {
  font: 400 11px/1.3 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  color: rgba(60, 60, 67, 0.58);
  margin-bottom: 16px;
}

.fm-preview-meta {
  width: 100%;
  margin: 0;
  padding: 10px 0 0;
  border-top: 0.5px solid rgba(60, 60, 67, 0.12);
  display: grid;
  gap: 8px;
}

.fm-preview-row {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 8px;
  font: 400 11px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-preview-row dt {
  color: rgba(60, 60, 67, 0.55);
}

.fm-preview-row dd {
  margin: 0;
  color: #1d1d1f;
  word-break: break-word;
}

.fm-preview-empty {
  margin-top: 48px;
  display: grid;
  gap: 6px;
  text-align: center;
  color: rgba(60, 60, 67, 0.55);
  font: 500 12px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-preview-empty small {
  font-weight: 400;
  font-size: 11px;
  color: rgba(60, 60, 67, 0.45);
}
</style>
