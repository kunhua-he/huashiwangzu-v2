import { onBeforeUnmount, reactive, watch, type Ref } from 'vue'
import type { FileEntry } from '@/shared/api/types'
import { fetchBlobByApiPath, fetchDownloadBlob, fetchFilePreview } from '@/shared/api/desktop'

export const FM_IMAGE_EXTS = new Set([
  'jpg', 'jpeg', 'jpe', 'jfif', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tif', 'tiff', 'avif',
])

export const FM_TEXT_EXTS = new Set([
  'txt', 'md', 'json', 'csv', 'log', 'xml', 'yaml', 'yml', 'ini', 'cfg', 'conf', 'env', 'sql', 'toml',
  'php', 'js', 'ts', 'jsx', 'tsx', 'css', 'scss', 'less', 'html', 'htm', 'vue',
  'py', 'java', 'go', 'rs', 'c', 'cpp', 'h', 'hpp', 'cs', 'rb', 'sh', 'bash', 'zsh',
])

export type FmPreviewMode = 'idle' | 'image' | 'pdf' | 'text' | 'fallback'

export interface FmPreviewMediaState {
  loading: boolean
  mode: FmPreviewMode
  text: string
  objectUrl: string
  truncated?: boolean
}

function extOf(item: FileEntry) {
  return String(item.format || '').toLowerCase().replace(/^\./, '')
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

async function resolveMediaBlob(
  data: Record<string, unknown>,
  fileId: number,
  preferStandardImage: boolean,
) {
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

function revokeUrl(state: { objectUrl: string }) {
  if (state.objectUrl) {
    URL.revokeObjectURL(state.objectUrl)
    state.objectUrl = ''
  }
}

export function useFmPreviewMedia(options: {
  viewMode: Ref<'grid' | 'list' | 'column' | 'gallery'>
  selected: Ref<FileEntry | null>
  items: Ref<FileEntry[]>
  columnPreviewItem: Ref<FileEntry | null>
}) {
  const galleryPreview = reactive<FmPreviewMediaState>({
    loading: false,
    mode: 'idle',
    text: '',
    objectUrl: '',
    truncated: false,
  })
  const columnMedia = reactive<FmPreviewMediaState>({
    loading: false,
    mode: 'idle',
    text: '',
    objectUrl: '',
  })
  const stripThumbs = reactive<Record<number, string>>({})

  let galleryToken = 0
  let columnToken = 0
  let stripToken = 0

  function resetGalleryPreview() {
    revokeUrl(galleryPreview)
    galleryPreview.loading = false
    galleryPreview.mode = 'idle'
    galleryPreview.text = ''
    galleryPreview.truncated = false
  }

  function resetColumnMedia() {
    revokeUrl(columnMedia)
    columnMedia.loading = false
    columnMedia.mode = 'idle'
    columnMedia.text = ''
  }

  function clearStripThumbs() {
    Object.keys(stripThumbs).forEach((key) => {
      const id = Number(key)
      if (stripThumbs[id]) URL.revokeObjectURL(stripThumbs[id])
      delete stripThumbs[id]
    })
  }

  async function loadGalleryPreview(item: FileEntry | null) {
    const token = ++galleryToken
    resetGalleryPreview()
    if (!item || item.is_folder) {
      galleryPreview.mode = 'fallback'
      return
    }
    galleryPreview.loading = true
    const ext = extOf(item)
    try {
      const data = await fetchFilePreview(item.id)
      if (token !== galleryToken) return
      if (!isRecord(data)) throw new Error('invalid preview')
      const content = asString(data.content)
      if (content) {
        galleryPreview.mode = 'text'
        galleryPreview.text = content
        galleryPreview.truncated = content.includes('--- File too long')
        return
      }
      const mime = asString(data.mime_type).toLowerCase()
      const looksImage = mime.startsWith('image/') || FM_IMAGE_EXTS.has(ext)
      const looksPdf = mime === 'application/pdf' || ext === 'pdf'
      if (looksImage) {
        const blob = await resolveMediaBlob(data, item.id, true)
        if (token !== galleryToken) return
        galleryPreview.objectUrl = URL.createObjectURL(blob)
        galleryPreview.mode = 'image'
        return
      }
      if (looksPdf) {
        const blob = await resolveMediaBlob(data, item.id, false)
        if (token !== galleryToken) return
        galleryPreview.objectUrl = URL.createObjectURL(blob)
        galleryPreview.mode = 'pdf'
        return
      }
      if (FM_TEXT_EXTS.has(ext)) {
        galleryPreview.mode = 'text'
        galleryPreview.text = content || '(空文件)'
        return
      }
      galleryPreview.mode = 'fallback'
    } catch {
      if (token !== galleryToken) return
      try {
        if (FM_IMAGE_EXTS.has(ext)) {
          const blob = await fetchDownloadBlob(item.id)
          if (token !== galleryToken) return
          galleryPreview.objectUrl = URL.createObjectURL(blob)
          galleryPreview.mode = 'image'
          return
        }
        if (ext === 'pdf') {
          const blob = await fetchDownloadBlob(item.id)
          if (token !== galleryToken) return
          galleryPreview.objectUrl = URL.createObjectURL(blob)
          galleryPreview.mode = 'pdf'
          return
        }
      } catch {
        // keep fallback
      }
      galleryPreview.mode = 'fallback'
    } finally {
      if (token === galleryToken) galleryPreview.loading = false
    }
  }

  async function loadStripThumbs(items: FileEntry[]) {
    const token = ++stripToken
    clearStripThumbs()
    const images = items.filter((item) => !item.is_folder && FM_IMAGE_EXTS.has(extOf(item))).slice(0, 24)
    for (const item of images) {
      if (token !== stripToken) return
      try {
        const data = await fetchFilePreview(item.id)
        if (token !== stripToken) return
        let blob: Blob
        if (isRecord(data)) {
          blob = await resolveMediaBlob(data, item.id, true)
        } else {
          blob = await fetchDownloadBlob(item.id, 'standard-image').catch(() => fetchDownloadBlob(item.id))
        }
        if (token !== stripToken) return
        stripThumbs[item.id] = URL.createObjectURL(blob)
      } catch {
        // keep icon
      }
    }
  }

  async function loadColumnMedia(item: FileEntry | null) {
    const token = ++columnToken
    resetColumnMedia()
    if (!item || item.is_folder) {
      columnMedia.mode = 'fallback'
      return
    }
    columnMedia.loading = true
    const ext = extOf(item)
    try {
      const data = await fetchFilePreview(item.id)
      if (token !== columnToken) return
      if (!isRecord(data)) throw new Error('invalid preview')
      const content = asString(data.content)
      if (content) {
        columnMedia.mode = 'text'
        columnMedia.text = content
        return
      }
      const mime = asString(data.mime_type).toLowerCase()
      if (mime.startsWith('image/') || FM_IMAGE_EXTS.has(ext)) {
        const blob = await resolveMediaBlob(data, item.id, true)
        if (token !== columnToken) return
        columnMedia.objectUrl = URL.createObjectURL(blob)
        columnMedia.mode = 'image'
        return
      }
      if (mime === 'application/pdf' || ext === 'pdf') {
        const blob = await resolveMediaBlob(data, item.id, false)
        if (token !== columnToken) return
        columnMedia.objectUrl = URL.createObjectURL(blob)
        columnMedia.mode = 'pdf'
        return
      }
      if (FM_TEXT_EXTS.has(ext)) {
        columnMedia.mode = 'text'
        columnMedia.text = content || '(空文件)'
        return
      }
      columnMedia.mode = 'fallback'
    } catch {
      if (token !== columnToken) return
      try {
        if (FM_IMAGE_EXTS.has(ext)) {
          const blob = await fetchDownloadBlob(item.id)
          if (token !== columnToken) return
          columnMedia.objectUrl = URL.createObjectURL(blob)
          columnMedia.mode = 'image'
          return
        }
        if (ext === 'pdf') {
          const blob = await fetchDownloadBlob(item.id)
          if (token !== columnToken) return
          columnMedia.objectUrl = URL.createObjectURL(blob)
          columnMedia.mode = 'pdf'
          return
        }
      } catch {
        // fallback icon
      }
      columnMedia.mode = 'fallback'
    } finally {
      if (token === columnToken) columnMedia.loading = false
    }
  }

  watch(
    () => [options.viewMode.value, options.selected.value?.id, options.selected.value?.format, options.selected.value?.is_folder] as const,
    () => {
      if (options.viewMode.value !== 'gallery') {
        galleryToken += 1
        resetGalleryPreview()
        return
      }
      void loadGalleryPreview(options.selected.value)
    },
    { immediate: true },
  )

  watch(
    () => [options.viewMode.value, options.items.value.map((item) => `${item.id}:${item.format || ''}`).join('|')] as const,
    () => {
      if (options.viewMode.value !== 'gallery') {
        stripToken += 1
        clearStripThumbs()
        return
      }
      void loadStripThumbs(options.items.value)
    },
    { immediate: true },
  )

  watch(
    () => [
      options.viewMode.value,
      options.columnPreviewItem.value?.id,
      options.columnPreviewItem.value?.format,
      options.columnPreviewItem.value?.is_folder,
    ] as const,
    () => {
      if (options.viewMode.value !== 'column') {
        columnToken += 1
        resetColumnMedia()
        return
      }
      void loadColumnMedia(options.columnPreviewItem.value)
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    galleryToken += 1
    columnToken += 1
    stripToken += 1
    resetGalleryPreview()
    resetColumnMedia()
    clearStripThumbs()
  })

  return {
    galleryPreview,
    columnMedia,
    stripThumbs,
  }
}
