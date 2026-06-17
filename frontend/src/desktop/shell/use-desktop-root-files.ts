import { onMounted, onUnmounted, ref } from 'vue'
import { fetchFileList } from '@/shared/api/desktop'
import type { FileEntry } from '@/shared/api/types'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import { openFileByRecord } from '@/desktop/app-registry/app-opener'
import { windowManager } from '@/desktop/window-manager/window-manager'
import { 格式化文件displayName } from '@/shared/files/display-name'

function displayName(文件: FileEntry) {
  return 文件.is_folder ? String(文件.file_name || '') : 格式化文件displayName(文件.file_name, 文件.format)
}

export function useDesktopRootFiles() {
  const 桌面文件列表 = ref<FileEntry[]>([])
  const { on, off } = useDesktopEventBus()

  async function loadDesktopFiles() {
    const 响应 = await fetchFileList(0)
    if (响应.success) 桌面文件列表.value = 响应.data?.items || []
  }

  function onFileRefresh(d?: unknown) {
    const payload = d as Record<string, unknown> | undefined
    const id = payload?.folderId as number | undefined
    if (id === undefined || id === 0) void loadDesktopFiles()
  }

  function openDesktopEntry(文件: FileEntry) {
    if (文件.is_folder || !文件.format) {
      windowManager.openWindow('desktop')
      return
    }
    openFileByRecord({ fileId: 文件.id, fileName: displayName(文件), format: 文件.format })
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

  return { 桌面文件列表, openDesktopEntry }
}
