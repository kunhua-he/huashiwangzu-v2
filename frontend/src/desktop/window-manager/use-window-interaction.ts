import { onUnmounted, ref, type Ref } from 'vue'
import { getDesktopWorkArea } from '@/desktop/config/desktop-chrome-metrics'

type ResizeDirection = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
type SnapKind = 'top'
type WindowGeometry = { x: number; y: number; width: number; height: number }
export type SnapPreview = { kind: SnapKind; x: number; y: number; width: number; height: number }
type InteractionConfig = {
  id: string; x: number; y: number; width: number; height: number; maximized: boolean
  minWidth: number; minHeight: number; rootEl: Ref<HTMLElement | null>
  preMaximizeState?: WindowGeometry
  activate: (id: string) => void; updatePosition: (id: string, x: number, y: number) => void
  updateGeometry: (id: string, x: number, y: number, width: number, height: number) => void
  maximize: (id: string, restoreState?: WindowGeometry) => void
}

const resizeDirections: ResizeDirection[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']
const SNAP_EDGE_SIZE = 18
const MAX_DRAG_RESTORE_THRESHOLD = 4

function clampDimension(value: number, min: number, max: number): number {
  if (max <= 0) return 0
  if (max < min) return max
  return Math.max(min, Math.min(value, max))
}

export function useWindowInteraction(readConfig: () => InteractionConfig) {
  const dragging = ref(false)
  const snapPreview = ref<SnapPreview | null>(null)
  const dragStart = ref({ x: 0, y: 0, winX: 0, winY: 0, winWidth: 0, winHeight: 0 })
  const resizeInfo = ref<{ direction: ResizeDirection; startX: number; startY: number; initialX: number; initialY: number; initialWidth: number; initialHeight: number } | null>(null)

  // 最大化拖拽还原状态
  const maxDragState = ref<{ startX: number; startY: number; triggered: boolean } | null>(null)

  const getBounds = () => {
    const parent = readConfig().rootEl.value?.parentElement
    const rect = parent?.getBoundingClientRect()
    const containerWidth = parent?.clientWidth ?? window.innerWidth
    const containerHeight = parent?.clientHeight ?? window.innerHeight
    const workArea = getDesktopWorkArea(containerWidth, containerHeight)
    return {
      containerLeft: rect?.left ?? 0,
      containerTop: rect?.top ?? 0,
      containerWidth,
      workArea,
    }
  }
  function resolveSnapPreview(e: MouseEvent): SnapPreview | null {
    const { containerTop, workArea } = getBounds()
    const pointerY = e.clientY - containerTop
    if (pointerY <= workArea.y + SNAP_EDGE_SIZE) {
      return { kind: 'top', ...workArea }
    }
    return null
  }
  function startDrag(e: MouseEvent) {
    const cfg = readConfig()

    // 最大化拖拽还原：记录起点，等待超过阈值后触发
    if (cfg.maximized) {
      cfg.activate(cfg.id)
      maxDragState.value = { startX: e.clientX, startY: e.clientY, triggered: false }
      document.addEventListener('mousemove', handleMaxDragMove)
      document.addEventListener('mouseup', stopMaxDrag)
      return
    }

    cfg.activate(cfg.id); dragging.value = true
    snapPreview.value = null
    dragStart.value = { x: e.clientX, y: e.clientY, winX: cfg.x, winY: cfg.y, winWidth: cfg.width, winHeight: cfg.height }
    document.addEventListener('mousemove', handleDragMove); document.addEventListener('mouseup', stopInteraction)
  }

  function handleMaxDragMove(e: MouseEvent) {
    if (!maxDragState.value || maxDragState.value.triggered) return
    const dx = e.clientX - maxDragState.value.startX
    const dy = e.clientY - maxDragState.value.startY
    const distance = Math.sqrt(dx * dx + dy * dy)
    if (distance < MAX_DRAG_RESTORE_THRESHOLD) return

    // 超过阈值 → 触发还原并进入拖拽模式
    maxDragState.value.triggered = true
    const cfg = readConfig()
    const restoreWidth = cfg.preMaximizeState?.width ?? cfg.minWidth * 2
    const restoreHeight = cfg.preMaximizeState?.height ?? cfg.minHeight * 2

    // 计算鼠标在标题栏的水平比例
    const titlebarEl = cfg.rootEl.value?.querySelector('.window-titlebar') as HTMLElement | null
    const titlebarWidth = titlebarEl?.offsetWidth ?? cfg.width
    const mouseRelativeX = e.clientX - (cfg.rootEl.value?.getBoundingClientRect().left ?? 0)
    const ratio = Math.max(0, Math.min(1, mouseRelativeX / titlebarWidth))

    // 还原窗口（调用 maximize 切换回普通态）
    cfg.maximize(cfg.id)

    // 还原后按比例定位窗口
    const { containerLeft, containerTop, workArea } = getBounds()
    const newX = Math.max(workArea.x, Math.min(e.clientX - containerLeft - restoreWidth * ratio, workArea.x + workArea.width - restoreWidth))
    const newY = Math.max(workArea.y, Math.min(e.clientY - containerTop - 16, workArea.y + workArea.height - restoreHeight))
    cfg.updateGeometry(cfg.id, Math.round(newX), Math.round(newY), restoreWidth, restoreHeight)

    // 清除最大化拖拽监听，进入常规拖拽
    document.removeEventListener('mousemove', handleMaxDragMove)
    document.removeEventListener('mouseup', stopMaxDrag)

    // 进入常规拖拽模式
    dragging.value = true
    snapPreview.value = null
    dragStart.value = { x: e.clientX, y: e.clientY, winX: Math.round(newX), winY: Math.round(newY), winWidth: restoreWidth, winHeight: restoreHeight }
    document.addEventListener('mousemove', handleDragMove)
    document.addEventListener('mouseup', stopInteraction)
  }

  function stopMaxDrag() {
    maxDragState.value = null
    document.removeEventListener('mousemove', handleMaxDragMove)
    document.removeEventListener('mouseup', stopMaxDrag)
  }

  function handleDragMove(e: MouseEvent) {
    if (!dragging.value) return
    const cfg = readConfig(), { workArea } = getBounds(), dx = e.clientX - dragStart.value.x, dy = e.clientY - dragStart.value.y
    cfg.updatePosition(
      cfg.id,
      Math.max(workArea.x, Math.min(dragStart.value.winX + dx, workArea.x + Math.max(0, workArea.width - cfg.width))),
      Math.max(workArea.y, Math.min(dragStart.value.winY + dy, workArea.y + Math.max(0, workArea.height - cfg.height))),
    )
    snapPreview.value = resolveSnapPreview(e)
  }
  function startResize(direction: ResizeDirection, e: MouseEvent) {
    const cfg = readConfig(); if (cfg.maximized) return
    cfg.activate(cfg.id)
    resizeInfo.value = { direction, startX: e.clientX, startY: e.clientY, initialX: cfg.x, initialY: cfg.y, initialWidth: cfg.width, initialHeight: cfg.height }
    document.addEventListener('mousemove', handleResizeMove); document.addEventListener('mouseup', stopInteraction)
  }
  function handleResizeMove(e: MouseEvent) {
    if (!resizeInfo.value) return
    const cfg = readConfig(), info = resizeInfo.value, { workArea } = getBounds(), dx = e.clientX - info.startX, dy = e.clientY - info.startY
    let { initialX: x, initialY: y, initialWidth: width, initialHeight: height } = info
    if (info.direction.includes('e')) width = clampDimension(info.initialWidth + dx, cfg.minWidth, workArea.x + workArea.width - info.initialX)
    if (info.direction.includes('s')) height = clampDimension(info.initialHeight + dy, cfg.minHeight, workArea.y + workArea.height - info.initialY)
    if (info.direction.includes('w')) {
      const rightEdge = info.initialX + info.initialWidth
      const nextX = Math.max(workArea.x, Math.min(info.initialX + dx, rightEdge))
      width = clampDimension(rightEdge - nextX, cfg.minWidth, rightEdge)
      x = rightEdge - width
    }
    if (info.direction.includes('n')) {
      const bottomEdge = info.initialY + info.initialHeight
      const nextY = Math.max(workArea.y, Math.min(info.initialY + dy, bottomEdge))
      height = clampDimension(bottomEdge - nextY, cfg.minHeight, bottomEdge)
      y = bottomEdge - height
    }
    cfg.updateGeometry(cfg.id, Math.round(x), Math.round(y), Math.round(width), Math.round(height))
  }
  function stopInteraction(e?: MouseEvent) {
    const preview = dragging.value && e ? resolveSnapPreview(e) : snapPreview.value
    if (dragging.value && preview) {
      const cfg = readConfig()
      cfg.maximize(cfg.id, {
        x: dragStart.value.winX,
        y: dragStart.value.winY,
        width: dragStart.value.winWidth,
        height: dragStart.value.winHeight,
      })
    }
    dragging.value = false; resizeInfo.value = null
    snapPreview.value = null
    document.removeEventListener('mousemove', handleDragMove); document.removeEventListener('mousemove', handleResizeMove); document.removeEventListener('mouseup', stopInteraction)
  }
  onUnmounted(() => {
    stopInteraction()
    stopMaxDrag()
  })
  return { resizeDirections, snapPreview, dragging, startDrag, startResize }
}
