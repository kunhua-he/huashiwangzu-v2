import { onMounted, onUnmounted } from 'vue'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import { startBoxSelection, updateBoxSelection, endBoxSelection, selectionRect } from '@/desktop/selection/selection-box-state'
import { clearSelection, setSelection } from '@/desktop/selection/desktop-selection-state'
import { updateDragOffset, enterFolder, leaveFolder, endDrag, dragState } from '@/desktop/drag-drop/drag-state'
import { clampIconPosition, setDropOverlayBatch } from '@/desktop/drag-drop/drag-tool'

function hitTestSelection(sel: { x: number; y: number; w: number; h: number }, e: MouseEvent) {
  const ids: string[] = []
  document.querySelectorAll('.desktop-icon-item').forEach(el => {
    const r = el.getBoundingClientRect()
    const overlaps = !(r.right < sel.x || r.left > sel.x + sel.w || r.bottom < sel.y || r.top > sel.y + sel.h)
    const key = overlaps ? el.getAttribute('data-selection-key') : null
    if (key) ids.push(key)
  })
  setSelection(ids, e.ctrlKey)
}

function detectHoveredFolder(e: MouseEvent) {
  const el = document.elementFromPoint(e.clientX, e.clientY)
  const folder = el?.closest?.('[data-folder]') as HTMLElement | null
  if (!folder) { leaveFolder(); return }
  const id = folder.getAttribute('data-selection-key')?.replace('file:', '') || ''
  if (id && !dragState.draggedIds.includes(`file:${id}`)) enterFolder(id)
  else leaveFolder()
}

function snapDraggedIcons(e: MouseEvent) {
  const primaryKey = dragState.draggedIds[0]
  if (!primaryKey) return
  const primary = document.querySelector(`[data-selection-key="${primaryKey}"]`)
  const originalRect = primary?.getBoundingClientRect()
  if (!originalRect) return
  const dropX = originalRect.left + e.clientX - dragState.originX
  const dropY = originalRect.top + e.clientY - dragState.originY
  const { x, y } = clampIconPosition(dropX, dropY)
  setDropOverlayBatch(primaryKey, x, y, dragState.draggedIds, dragState.offsetList)
  dragState.offsetList.forEach(({ id, dx, dy }) => {
    const el = document.querySelector(`[data-selection-key="${id}"]`) as HTMLElement | null
    if (el) el.style.transform = `translate(${x + dx - originalRect.left}px, ${y + dy - originalRect.top}px)`
  })
}

export function useDesktopPointer() {
  const { emit } = useDesktopEventBus()

  function handleDesktopMouseDown(e: MouseEvent) {
    if (e.target !== e.currentTarget) return
    if (!e.ctrlKey) clearSelection()
    startBoxSelection(e.clientX, e.clientY)
  }

  function handleDesktopMouseMove(e: MouseEvent) {
    if (dragState.isDragging) {
      updateDragOffset(e.clientX - dragState.originX, e.clientY - dragState.originY)
      detectHoveredFolder(e)
      return
    }
    if (!selectionRect.value.w && !selectionRect.value.h) return
    updateBoxSelection(e.clientX, e.clientY)
    const sel = selectionRect.value
    if (sel.w >= 4 || sel.h >= 4) hitTestSelection(sel, e)
  }

  function handleDesktopMouseUp(e: MouseEvent) {
    if (dragState.isDragging) {
      const targetFolder = dragState.dragOverId
      if (targetFolder) emit('desktop:move-to-folder', { ids: dragState.draggedIds, targetFolderId: targetFolder })
      else snapDraggedIcons(e)
      endDrag()
      return
    }
    endBoxSelection()
  }

  onMounted(() => {
    window.addEventListener('mousemove', handleDesktopMouseMove)
    window.addEventListener('mouseup', handleDesktopMouseUp)
  })
  onUnmounted(() => {
    window.removeEventListener('mousemove', handleDesktopMouseMove)
    window.removeEventListener('mouseup', handleDesktopMouseUp)
  })
  return { handleDesktopMouseDown }
}
