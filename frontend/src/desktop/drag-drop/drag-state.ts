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
  originLeft: number
  originTop: number
  offsetList: { id: string; dx: number; dy: number; baseLeft: number; baseTop: number }[]
}

const dragState = reactive<DragState>({
  isDragging: false,
  draggedIds: [],
  dragOverId: null,
  originX: 0, originY: 0,
  originLeft: 0, originTop: 0,
  offsetList: [],
})

let _hoverTimer: ReturnType<typeof setTimeout> | null = null

function getTranslateOffset(el: Element): { x: number; y: number } {
  const transform = window.getComputedStyle(el).transform
  if (!transform || transform === 'none') return { x: 0, y: 0 }
  const matrix3d = transform.match(/^matrix3d\((.+)\)$/)
  if (matrix3d) {
    const parts = matrix3d[1].split(',').map(part => Number(part.trim()))
    return { x: Number.isFinite(parts[12]) ? parts[12] : 0, y: Number.isFinite(parts[13]) ? parts[13] : 0 }
  }
  const matrix = transform.match(/^matrix\((.+)\)$/)
  if (!matrix) return { x: 0, y: 0 }
  const parts = matrix[1].split(',').map(part => Number(part.trim()))
  return { x: Number.isFinite(parts[4]) ? parts[4] : 0, y: Number.isFinite(parts[5]) ? parts[5] : 0 }
}

export function startDrag(ids: string[], x: number, y: number): void {
  dragState.isDragging = true
  dragState.draggedIds = ids
  dragState.originX = x
  dragState.originY = y
  const primaryEl = document.querySelector(`[data-selection-key="${ids[0]}"]`)
  const primaryRect = primaryEl?.getBoundingClientRect()
  if (!primaryRect) { endDrag(); return }
  dragState.originLeft = primaryRect.left
  dragState.originTop = primaryRect.top
  dragState.offsetList = ids.map(id => {
    const el = document.querySelector(`[data-selection-key="${id}"]`)
    const r = el?.getBoundingClientRect()
    const offset = el ? getTranslateOffset(el) : { x: 0, y: 0 }
    return {
      id,
      dx: (r?.left ?? 0) - primaryRect.left,
      dy: (r?.top ?? 0) - primaryRect.top,
      baseLeft: (r?.left ?? 0) - offset.x,
      baseTop: (r?.top ?? 0) - offset.y,
    }
  })
  document.body.classList.add('desktop-dragging')
}

export function updateDragOffset(dx: number, dy: number): void {
  if (!dragState.isDragging) return
  dragState.offsetList.forEach(item => {
    const el = document.querySelector(`[data-selection-key="${item.id}"]`) as HTMLElement | null
    if (!el) return
    const previewLeft = dragState.originLeft + item.dx + dx
    const previewTop = dragState.originTop + item.dy + dy
    el.style.position = 'relative'
    el.style.zIndex = '999'
    el.style.pointerEvents = 'none'
    el.style.transition = 'none'
    el.style.transform = `translate(${previewLeft - item.baseLeft}px, ${previewTop - item.baseTop}px)`
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

export function endDrag(options: { keepTransform?: boolean } = {}): void {
  const draggedIds = new Set(dragState.draggedIds)
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
    ;(el as HTMLElement).style.transition = ''
    if (!options.keepTransform && draggedIds.has(el.getAttribute('data-selection-key') || '')) {
      ;(el as HTMLElement).style.transform = ''
    }
  })
}

export { dragState }
