/**
 * 桌面图标选中状态 — 共享给桌面壳和图标网格
 */
import { reactive, computed } from 'vue'

interface DesktopSelectionState {
  ids: string[]
}

const state = reactive<DesktopSelectionState>({ ids: [] })

export function select(id: string): void { state.ids = [id] }

export function appendSelection(id: string): void {
  if (!state.ids.includes(id)) state.ids.push(id)
}

export function setSelection(ids: string[], append = false): void {
  state.ids = append ? [...new Set([...state.ids, ...ids])] : ids
}

export function clearSelection(): void { state.ids = [] }

export function toggleSelection(id: string): void {
  const idx = state.ids.indexOf(id)
  idx >= 0 ? state.ids.splice(idx, 1) : state.ids.push(id)
}

export function isSelected(id: string): boolean {
  return state.ids.includes(id)
}

export const selectionCount = computed(() => state.ids.length)
export const selectedIds = computed(() => [...state.ids])
export const hasMultipleSelection = computed(() => state.ids.length > 1)
