import { onMounted, onUnmounted, ref } from 'vue'
import { fetchFileList } from '@/shared/api/desktop'
import type { FileEntry } from '@/shared/api/types'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import { openAppById, openFileByRecord } from '@/desktop/app-registry/app-opener'
import { formatFileDisplayName } from '@/shared/files/display-name'
import { createLoadState, failLoading, finishLoading, startLoading } from '@/shared/composables/use-load-state'

function displayName(file: FileEntry) {
  return file.is_folder ? String(file.file_name || '') : formatFileDisplayName(file.file_name, file.format)
}

export function useDesktopRootFiles() {
  const desktopFileList = ref<FileEntry[]>([])
  const desktopFileLoadState = createLoadState<FileEntry[]>([])
  const { on, off } = useDesktopEventBus()

  async function loadDesktopFiles() {
    startLoading(desktopFileLoadState)
    try {
      const data = await fetchFileList(0)
      const items = data?.items || []
      desktopFileList.value = items
      finishLoading(desktopFileLoadState, items)
    } catch (error: unknown) {
      failLoading(desktopFileLoadState, error, '桌面文件加载失败')
    }
  }

  function onFileRefresh(d?: unknown) {
    const payload = d as Record<string, unknown> | undefined
    const id = payload?.folderId as number | undefined
    if (id === undefined || id === 0) void loadDesktopFiles()
  }

  function openDesktopEntry(file: FileEntry) {
    if (file.is_folder || !file.format) {
      openAppById('desktop', {
        folderId: file.id,
        folderName: displayName(file),
      })
      return
    }
    openFileByRecord({ fileId: file.id, fileName: displayName(file), format: file.format })
  }

  function openFileFromEvent(payload: { fileId: number; fileName?: string; format?: string; page?: number }) {
    if (!payload?.fileId) return
    openFileByRecord({
      fileId: payload.fileId,
      fileName: payload.fileName || '',
      format: payload.format || '',
      page: payload.page,
    })
  }

  onMounted(() => {
    void loadDesktopFiles()
    on('refresh:file-list', onFileRefresh)
    on('file:uploaded', onFileRefresh)
    on('file:created', onFileRefresh)
    on('file:open', openFileFromEvent)
  })
  onUnmounted(() => {
    off('refresh:file-list', onFileRefresh)
    off('file:uploaded', onFileRefresh)
    off('file:created', onFileRefresh)
    off('file:open', openFileFromEvent)
  })

  return { desktopFileList, desktopFileLoadState, loadDesktopFiles, openDesktopEntry }
}
