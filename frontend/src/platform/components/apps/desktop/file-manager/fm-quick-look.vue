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
      <section class="fm-ql-panel" :class="`mode-${preview.mode}`" tabindex="-1">
        <header class="fm-ql-head">
          <strong>{{ displayName(item) }}</strong>
          <button type="button" class="fm-ql-close" aria-label="关闭" @click="$emit('close')">×</button>
        </header>

        <div class="fm-ql-body" :class="{ 'has-media': preview.mode === 'image' || preview.mode === 'pdf' || preview.mode === 'text' }">
          <div v-if="preview.loading" class="fm-ql-state">加载预览…</div>

          <div v-else-if="preview.error" class="fm-ql-fallback">
            <FileVisualIcon
              :kind="item.is_folder || !item.format ? 'folder' : 'file'"
              :extension="item.format || ''"
              :size="96"
            />
            <div class="fm-ql-name">{{ displayName(item) }}</div>
            <div class="fm-ql-meta">{{ preview.error }}</div>
          </div>

          <img
            v-else-if="preview.mode === 'image' && preview.objectUrl"
            class="fm-ql-image"
            :src="preview.objectUrl"
            :alt="displayName(item)"
          >

          <iframe
            v-else-if="preview.mode === 'pdf' && preview.objectUrl"
            class="fm-ql-pdf"
            :src="preview.objectUrl"
            title="PDF 预览"
          />

          <pre v-else-if="preview.mode === 'text'" class="fm-ql-text">{{ preview.text }}</pre>

          <div v-else class="fm-ql-fallback">
            <FileVisualIcon
              :kind="item.is_folder || !item.format ? 'folder' : 'file'"
              :extension="item.format || ''"
              :size="112"
            />
            <div class="fm-ql-name">{{ displayName(item) }}</div>
            <div class="fm-ql-meta">
              {{ item.is_folder ? '文件夹' : ((item.format || '文件').toUpperCase()) }}
              <template v-if="!item.is_folder"> · {{ formatSize(item.file_size) }}</template>
            </div>
            <div class="fm-ql-hint">此类型暂不支持内联预览</div>
          </div>
        </div>

        <footer class="fm-ql-foot">
          <div class="fm-ql-foot-meta">
            <span v-if="!item.is_folder">{{ formatSize(item.file_size) }}</span>
            <span v-if="preview.truncated" class="fm-ql-truncated">已截断</span>
            <span class="fm-ql-hint-inline">空格 关闭 · Enter 打开</span>
          </div>
          <div class="fm-ql-foot-actions">
            <button type="button" class="fm-ql-btn" @click="$emit('open', item)">打开</button>
            <button type="button" class="fm-ql-btn primary" @click="$emit('close')">完成</button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { reactive, watch, onBeforeUnmount } from 'vue'
import FileVisualIcon from '@/shared/components/file-visual-icon.vue'
import { fetchBlobByApiPath, fetchDownloadBlob, fetchFilePreview } from '@/shared/api/desktop'
import type { FileEntry } from '@/shared/api/types'

const props = defineProps<{
  visible: boolean
  item: FileEntry | null
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

defineEmits<{
  (e: 'close'): void
  (e: 'open', item: FileEntry): void
}>()

type PreviewMode = 'idle' | 'image' | 'pdf' | 'text' | 'fallback'

const preview = reactive({
  loading: false,
  mode: 'idle' as PreviewMode,
  text: '',
  objectUrl: '' as string,
  error: '',
  truncated: false,
})

let loadToken = 0

function revokeObjectUrl() {
  if (preview.objectUrl) {
    URL.revokeObjectURL(preview.objectUrl)
    preview.objectUrl = ''
  }
}

function resetPreview() {
  revokeObjectUrl()
  preview.loading = false
  preview.mode = 'idle'
  preview.text = ''
  preview.error = ''
  preview.truncated = false
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function extOf(item: FileEntry): string {
  return String(item.format || '').toLowerCase().replace(/^\./, '')
}

const IMAGE_EXTS = new Set([
  'jpg', 'jpeg', 'jpe', 'jfif', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tif', 'tiff', 'avif',
])
const TEXT_EXTS = new Set([
  'txt', 'md', 'json', 'csv', 'log', 'xml', 'yaml', 'yml', 'ini', 'cfg', 'conf', 'env', 'sql', 'toml',
  'php', 'js', 'ts', 'jsx', 'tsx', 'css', 'scss', 'less', 'html', 'htm', 'vue',
  'py', 'java', 'go', 'rs', 'c', 'cpp', 'h', 'hpp', 'cs', 'rb', 'sh', 'bash', 'zsh',
])

async function resolveMediaBlob(data: Record<string, unknown>, fileId: number, preferStandardImage: boolean) {
  const downloadUrl = asString(data.download_url)
  if (downloadUrl) {
    try {
      return await fetchBlobByApiPath(downloadUrl)
    } catch {
      // fall through
    }
  }
  if (preferStandardImage) {
    try {
      return await fetchDownloadBlob(fileId, 'standard-image')
    } catch {
      // fall through
    }
  }
  return await fetchDownloadBlob(fileId)
}

async function loadPreview(item: FileEntry) {
  const token = ++loadToken
  resetPreview()
  if (item.is_folder) {
    preview.mode = 'fallback'
    return
  }

  preview.loading = true
  const ext = extOf(item)
  try {
    // Prefer structured preview API (text content / image derivative urls)
    const data = await fetchFilePreview(item.id)
    if (token !== loadToken) return
    if (!isRecord(data)) throw new Error('invalid preview')

    const content = asString(data.content)
    if (content) {
      preview.mode = 'text'
      preview.text = content
      preview.truncated = content.includes('--- File too long')
      return
    }

    const mime = asString(data.mime_type).toLowerCase()
    const looksImage = mime.startsWith('image/') || IMAGE_EXTS.has(ext)
    const looksPdf = mime === 'application/pdf' || ext === 'pdf'

    if (looksImage) {
      const blob = await resolveMediaBlob(data, item.id, true)
      if (token !== loadToken) return
      preview.objectUrl = URL.createObjectURL(blob)
      preview.mode = 'image'
      return
    }

    if (looksPdf) {
      const blob = await resolveMediaBlob(data, item.id, false)
      if (token !== loadToken) return
      preview.objectUrl = URL.createObjectURL(blob)
      preview.mode = 'pdf'
      return
    }

    // Unknown binary from API — still try common fallbacks by extension
    if (TEXT_EXTS.has(ext)) {
      preview.mode = 'text'
      preview.text = content || '(空文件)'
      return
    }
    preview.mode = 'fallback'
  } catch (error: unknown) {
    if (token !== loadToken) return
    // Fallback path when preview endpoint rejects (office/size) but download may still work for image/pdf
    try {
      if (IMAGE_EXTS.has(ext)) {
        const blob = await fetchDownloadBlob(item.id)
        if (token !== loadToken) return
        preview.objectUrl = URL.createObjectURL(blob)
        preview.mode = 'image'
        return
      }
      if (ext === 'pdf') {
        const blob = await fetchDownloadBlob(item.id)
        if (token !== loadToken) return
        preview.objectUrl = URL.createObjectURL(blob)
        preview.mode = 'pdf'
        return
      }
    } catch {
      // keep error below
    }
    const message = error instanceof Error && error.message ? error.message : '无法预览此文件'
    preview.error = message
    preview.mode = 'fallback'
  } finally {
    if (token === loadToken) preview.loading = false
  }
}

watch(
  () => [props.visible, props.item?.id, props.item?.is_folder, props.item?.format] as const,
  ([visible, id]) => {
    if (!visible || !props.item || id == null) {
      loadToken += 1
      resetPreview()
      return
    }
    void loadPreview(props.item)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  loadToken += 1
  resetPreview()
})
</script>

<style scoped>
.fm-ql-overlay {
  position: fixed;
  inset: 0;
  z-index: 13000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(12px) saturate(140%);
  -webkit-backdrop-filter: blur(12px) saturate(140%);
}

.fm-ql-panel {
  width: min(520px, 100%);
  max-height: min(86vh, 860px);
  border-radius: 14px;
  border: 0.5px solid rgba(60, 60, 67, 0.16);
  background: color-mix(in srgb, #f6f6f8 88%, white);
  box-shadow: 0 22px 56px rgba(0, 0, 0, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.55);
  overflow: hidden;
  color: #1d1d1f;
  display: flex;
  flex-direction: column;
}

.fm-ql-panel.mode-image,
.fm-ql-panel.mode-pdf,
.fm-ql-panel.mode-text {
  width: min(920px, 96vw);
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
  flex-shrink: 0;
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
  min-height: 180px;
  max-height: min(68vh, 680px);
  overflow: auto;
  display: grid;
  place-items: center;
  padding: 24px 20px 18px;
  background: #fff;
}

.fm-ql-body.has-media {
  padding: 0;
  place-items: stretch;
  background: #0f0f10;
}

.fm-ql-state {
  color: rgba(60, 60, 67, 0.62);
  font: 400 13px/1.4 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-ql-fallback {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 20px;
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
  text-align: center;
}

.fm-ql-hint {
  font-size: 11px;
  opacity: 0.9;
}

.fm-ql-image {
  width: 100%;
  height: min(68vh, 680px);
  object-fit: contain;
  background:
    linear-gradient(45deg, #1a1a1c 25%, transparent 25%),
    linear-gradient(-45deg, #1a1a1c 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #1a1a1c 75%),
    linear-gradient(-45deg, transparent 75%, #1a1a1c 75%);
  background-size: 24px 24px;
  background-position: 0 0, 0 12px, 12px -12px, -12px 0;
  background-color: #121214;
}

.fm-ql-pdf {
  width: 100%;
  height: min(68vh, 680px);
  border: 0;
  background: #2b2b2d;
}

.fm-ql-text {
  margin: 0;
  width: 100%;
  height: min(68vh, 680px);
  overflow: auto;
  padding: 16px 18px;
  box-sizing: border-box;
  background: #fbfbfd;
  color: #1d1d1f;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.fm-ql-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px 12px;
  border-top: 0.5px solid rgba(60, 60, 67, 0.12);
  background: color-mix(in srgb, #f2f2f4 88%, white);
  flex-shrink: 0;
}

.fm-ql-foot-meta {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  color: rgba(60, 60, 67, 0.58);
  font: 400 11px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-ql-truncated {
  color: #c93400;
}

.fm-ql-hint-inline {
  opacity: 0.85;
}

.fm-ql-foot-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
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
