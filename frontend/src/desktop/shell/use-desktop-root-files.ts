import { onMounted, onUnmounted, ref } from 'vue'
import { fetchFileList } from '@/shared/api/desktop'
import type { FileEntry } from '@/shared/api/types'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import { openFileByRecord } from '@/desktop/app-registry/app-opener'
import { windowManager } from '@/desktop/window-manager/window-manager'
import { formatFileDisplayName } from '@/shared/files/display-name'

function displayName(file: FileEntry) {
  return file.is_folder ? String(file.file_name || '') : formatFileDisplayName(file.file_name, file.format)
}

export function useDesktopRootFiles() {
  const desktopFileList = ref<FileEntry[]>([])
  const { on, off } = useDesktopEventBus()

  async function loadDesktopFiles() {
    try {
      const data = await fetchFileList(0)
      desktopFileList.value = data?.items || []
    } catch {
      desktopFileList.value = []
    }
  }

  function onFileRefresh(d?: unknown) {
    const payload = d as Record<string, unknown> | undefined
    const id = payload?.folderId as number | undefined
    if (id === undefined || id === 0) void loadDesktopFiles()
  }

  function openDesktopEntry(file: FileEntry) {
    if (file.is_folder || !file.format) {
      windowManager.openWindow('desktop', {
        folderId: file.id,
        folderName: displayName(file),
      })
      return
    }
    openFileByRecord({ fileId: file.id, fileName: displayName(file), format: file.format })
  }

  onMounted(() => {
    void loadDesktopFiles()
    on('refresh:file-list', onFileRefresh)
    on('file:uploaded', onFileRefresh)
    on('file:created', onFileRefresh)
  })
  onUnmounted(() => {
    off('refresh:file-list', onFileRefresh)
    off('file:uploaded', onFileRefresh)
    off('file:created', onFileRefresh)
  })

  return { desktopFileList, openDesktopEntry }
}
