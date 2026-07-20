import { onBeforeUnmount } from 'vue'
import type { FileEntry } from '@/shared/api/types'
import { startDrag, dragState } from '@/desktop/drag-drop/drag-state'

export function selectionKeyOf(item: FileEntry) {
  return (item.is_folder ? 'folder' : 'file') + ':' + item.id
}

export function useFmEntryInteraction(options: {
  getItems: () => FileEntry[]
  getSelectedIds: () => number[]
  onSelect: (item: FileEntry, opts?: { additive?: boolean; range?: boolean }) => void
  onOpen: (item: FileEntry) => void
  onColumnSelect?: (item: FileEntry, columnIndex: number) => void
  onColumnOpen?: (item: FileEntry, columnIndex: number) => void
}) {
  let suppressNextClick = false
  let pendingDrag: { key: string; keys: string[]; startX: number; startY: number } | null = null

  function resolveDragKeys(item: FileEntry): string[] {
    const primary = selectionKeyOf(item)
    const selectedIds = options.getSelectedIds()
    if (selectedIds.includes(item.id) && selectedIds.length > 1) {
      const byId = new Map(options.getItems().map((entry) => [entry.id, entry]))
      const keys = selectedIds
        .map((id) => byId.get(id))
        .filter((entry): entry is FileEntry => Boolean(entry))
        .map(selectionKeyOf)
      if (keys.length) {
        return [primary, ...keys.filter((key) => key !== primary)]
      }
    }
    return [primary]
  }

  function clearPendingDrag() {
    document.removeEventListener('mousemove', handlePendingDragMove)
    document.removeEventListener('mouseup', clearPendingDrag)
    pendingDrag = null
  }

  function handlePendingDragMove(e: MouseEvent) {
    if (!pendingDrag) return
    const dx = e.clientX - pendingDrag.startX
    const dy = e.clientY - pendingDrag.startY
    if (Math.abs(dx) < 4 && Math.abs(dy) < 4) return
    suppressNextClick = true
    startDrag(pendingDrag.keys, pendingDrag.startX, pendingDrag.startY, { copyMode: e.altKey })
    clearPendingDrag()
  }

  function handleEntryMouseDown(item: FileEntry, e: MouseEvent) {
    if (e.button !== 0) return
    pendingDrag = {
      key: selectionKeyOf(item),
      keys: resolveDragKeys(item),
      startX: e.clientX,
      startY: e.clientY,
    }
    document.addEventListener('mousemove', handlePendingDragMove)
    document.addEventListener('mouseup', clearPendingDrag)
  }

  function consumeSuppressedClick(e: MouseEvent): boolean {
    if (!suppressNextClick) return false
    e.preventDefault()
    e.stopPropagation()
    suppressNextClick = false
    return true
  }

  function handleClick(item: FileEntry, e: MouseEvent) {
    if (consumeSuppressedClick(e)) return
    options.onSelect(item, { additive: e.metaKey || e.ctrlKey, range: e.shiftKey })
  }

  function handleDoubleClick(item: FileEntry, e: MouseEvent) {
    if (consumeSuppressedClick(e)) return
    options.onOpen(item)
  }

  function handleColumnClick(item: FileEntry, columnIndex: number, e: MouseEvent) {
    if (consumeSuppressedClick(e)) return
    options.onColumnSelect?.(item, columnIndex)
    options.onSelect(item, { additive: e.metaKey || e.ctrlKey, range: e.shiftKey })
  }

  function handleColumnDoubleClick(item: FileEntry, columnIndex: number, e: MouseEvent) {
    if (consumeSuppressedClick(e)) return
    if (item.is_folder) {
      options.onColumnOpen?.(item, columnIndex)
      return
    }
    options.onOpen(item)
  }

  function isDropTarget(item: FileEntry) {
    if (!item.is_folder || !dragState.isDragging || !dragState.dragOverId) return false
    if (dragState.dragOverId !== String(item.id)) return false
    if (dragState.draggedIds.some((key) => key === `folder:${item.id}` || key.endsWith(`:${item.id}`))) {
      return false
    }
    return true
  }

  onBeforeUnmount(() => {
    clearPendingDrag()
  })

  return {
    handleEntryMouseDown,
    handleClick,
    handleDoubleClick,
    handleColumnClick,
    handleColumnDoubleClick,
    isDropTarget,
    clearPendingDrag,
  }
}
