/**
 * 拖拽状态 — 桌面图标拖拽移入文件夹
 *
 * - 拖拽时记录被拖图标列表（支持框选后批量拖）
 * - 悬停文件夹 150ms 延迟触发高亮（防路过误触）
 * - 拖拽过程中禁用其他图标的 hover 样式
 */
import { reactive } from 'vue'

interface DragState {
  isDragging: boolean
  draggedIds: string[]
  dragOverId: string | null
  originX: number
  originY: number
  offsetList: { id: string; dx: number; dy: number }[]
}

const dragState = reactive<DragState>({
  isDragging: false,
  draggedIds: [],
  dragOverId: null,
  originX: 0, originY: 0,
  offsetList: [],
})

let _hoverTimer: ReturnType<typeof setTimeout> | null = null

export function startDrag(ids: string[], x: number, y: number): void {
  dragState.isDragging = true
  dragState.draggedIds = ids
  dragState.originX = x
  dragState.originY = y
  const primaryEl = document.querySelector(`[data-selection-key="${ids[0]}"]`)
  const primaryRect = primaryEl?.getBoundingClientRect()
  if (!primaryRect) { endDrag(); return }
  dragState.offsetList = ids.map(id => {
    const el = document.querySelector(`[data-selection-key="${id}"]`)
    const r = el?.getBoundingClientRect()
    return { id, dx: (r?.left ?? 0) - primaryRect.left, dy: (r?.top ?? 0) - primaryRect.top }
  })
  document.body.classList.add('desktop-dragging')
}

export function updateDragOffset(dx: number, dy: number): void {
  if (!dragState.isDragging) return
  dragState.offsetList.forEach(item => {
    const el = document.querySelector(`[data-selection-key="${item.id}"]`) as HTMLElement | null
    if (!el) return
    el.style.position = 'fixed'
    el.style.left = (dragState.originX + item.dx + dx) + 'px'
    el.style.top = (dragState.originY + item.dy + dy) + 'px'
    el.style.zIndex = '999'
    el.style.pointerEvents = 'none'
  })
}

export function enterFolder(id: string): void {
  if (_hoverTimer) clearTimeout(_hoverTimer)
  _hoverTimer = setTimeout(() => { dragState.dragOverId = id }, 150)
}

export function leaveFolder(): void {
  if (_hoverTimer) clearTimeout(_hoverTimer)
  dragState.dragOverId = null
}

export function endDrag(): void {
  dragState.isDragging = false
  dragState.draggedIds = []
  dragState.dragOverId = null
  dragState.offsetList = []
  if (_hoverTimer) clearTimeout(_hoverTimer)
  document.body.classList.remove('desktop-dragging')
  document.querySelectorAll('[data-selection-key]').forEach(el => {
    (el as HTMLElement).style.position = ''
    ;(el as HTMLElement).style.left = ''
    ;(el as HTMLElement).style.top = ''
    ;(el as HTMLElement).style.zIndex = ''
    ;(el as HTMLElement).style.pointerEvents = ''
  })
}

export { dragState }
