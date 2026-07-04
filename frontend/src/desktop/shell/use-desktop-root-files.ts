import { onMounted, onUnmounted, ref } from 'vue'
import { fetchFileList } from '@/shared/api/desktop'
import type { FileEntry } from '@/shared/api/types'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import { openFileByRecord } from '@/desktop/app-registry/app-opener'
import { windowManager } from '@/desktop/window-manager/window-manager'
import { formatFileDisplayName } from '@/shared/files/display-name'
import { createLoadState, failLoading, finishLoading, startLoading } from '@/shared/composables/use-load-state'
import { ElMessage } from 'element-plus'
import { getApp } from '@/desktop/app-registry/app-registry'
import { getOpenWindowFailureMessage } from '@/desktop/app-registry/app-visibility'

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
      const windowId = windowManager.openWindow('desktop', {
        folderId: file.id,
        folderName: displayName(file),
      })
      if (!windowId) ElMessage.info(getOpenWindowFailureMessage(getApp('desktop')))
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

  return { desktopFileList, desktopFileLoadState, loadDesktopFiles, openDesktopEntry }
}
