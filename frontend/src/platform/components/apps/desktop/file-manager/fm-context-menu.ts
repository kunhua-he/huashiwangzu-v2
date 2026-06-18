import { ref, type ComputedRef } from 'vue'
import { buildFileMenu, buildFolderMenu } from '@/desktop/context-menu/file-context-menu'
import { useCreatableFormats } from '@/shared/composables/use-creatable-formats'
import type { FileEntry } from '@/shared/api/types'
import type { DesktopFileManagerMenuItem } from './types'

interface ContextMenuDeps {
  canWrite: ComputedRef<boolean>
}

export function createContextMenu(deps: ContextMenuDeps) {
  const { creatableFormats } = useCreatableFormats()
  const ctxVisible = ref(false)
  const ctxX = ref(0)
  const ctxY = ref(0)
  const ctxItems = ref<DesktopFileManagerMenuItem[]>([])
  const ctxTarget = ref<FileEntry | null>(null)

  function closeContextMenu() {
    ctxVisible.value = false
  }

  function showMenu(itemsValue: DesktopFileManagerMenuItem[], e: MouseEvent) {
    ctxItems.value = itemsValue
    ctxX.value = e.clientX
    ctxY.value = e.clientY
    ctxVisible.value = true
  }

  function handleBlankContextMenu(e: MouseEvent) {
    ctxTarget.value = null
    const items: DesktopFileManagerMenuItem[] = [
      { key: 'refresh', label: '刷新', icon: '↻' },
      { key: 'upload-file', label: '上传', icon: '↑', disabled: !deps.canWrite.value },
      { key: 'create-folder', label: '新建文件夹', icon: '+', disabled: !deps.canWrite.value },
    ]
    if (deps.canWrite.value) {
      items.splice(3, 0, ...creatableFormats.value.map(format => ({
        key: `create-file:${format.extension}`,
        label: `新建文件：${format.label}`,
        icon: '📄',
      })))
    }
    showMenu(items, e)
  }

  function handleItemMenu(item: FileEntry, e: MouseEvent) {
    ctxTarget.value = item
    const builtMenu = item.is_folder
      ? buildFolderMenu(deps.canWrite.value, () => []) as DesktopFileManagerMenuItem[]
      : buildFileMenu(deps.canWrite.value, () => []) as DesktopFileManagerMenuItem[]

    // Replace 'details' key from external module with 'properties', or append if missing
    const detailsIdx = builtMenu.findIndex(m => m.key === 'details')
    const propEntry: DesktopFileManagerMenuItem = { key: 'properties', label: '属性', icon: 'ℹ️' }
    if (detailsIdx >= 0) {
      builtMenu[detailsIdx] = propEntry
    } else {
      builtMenu.push(propEntry)
    }

    showMenu(builtMenu, e)
  }

  function showSelectedMenu() {
    if (!ctxTarget.value) return
    const fakeEvent = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 280, clientY: 180 })
    handleItemMenu(ctxTarget.value, fakeEvent)
  }

  return {
    ctxVisible,
    ctxX,
    ctxY,
    ctxItems,
    ctxTarget,
    closeContextMenu,
    showMenu,
    handleBlankContextMenu,
    handleItemMenu,
    showSelectedMenu,
  }
}
