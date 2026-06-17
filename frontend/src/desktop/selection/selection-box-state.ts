/**
 * 框选状态 — 矩形选区起点/终点/是否激活
 */
import { reactive, computed } from 'vue'

interface SelectionBoxState {
  active: boolean
  startX: number
  startY: number
  currentX: number
  currentY: number
}

const state = reactive<SelectionBoxState>({
  active: false,
  startX: 0, startY: 0,
  currentX: 0, currentY: 0,
})

export function startBoxSelection(x: number, y: number): void {
  state.active = true
  state.startX = x
  state.startY = y
  state.currentX = x
  state.currentY = y
}

export function updateBoxSelection(x: number, y: number): void {
  if (!state.active) return
  state.currentX = x
  state.currentY = y
}

export function endBoxSelection(): void {
  state.active = false
}

export const selectionRect = computed(() => {
  const x = Math.min(state.startX, state.currentX)
  const y = Math.min(state.startY, state.currentY)
  const w = Math.abs(state.currentX - state.startX)
  const h = Math.abs(state.currentY - state.startY)
  return { x, y, w, h }
})

export const isBoxSelectionActive = computed(() => state.active)

export const isBoxSelectionValid = computed(() =>
  state.active && (selectionRect.value.w > 4 || selectionRect.value.h > 4)
)
