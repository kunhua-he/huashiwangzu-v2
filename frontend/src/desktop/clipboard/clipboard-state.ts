/**
 * 剪贴板状态 — 复制/剪切/粘贴
 *
 * 使用说明：
 * - 复制/剪切时自动清空上一次剪贴板状态
 * - 剪切后图标置半透明，粘贴后恢复
 * - 再次复制/剪切自动清除上一次
 */

import { reactive, computed } from 'vue'

export interface ClipboardItem {
  id: number
  type: 'file' | 'folder'
  name: string
  originalPath?: string
}

interface ClipboardState {
  type: 'copy' | 'cut' | null
  items: ClipboardItem[]
}

const state = reactive<ClipboardState>({
  type: null,
  items: [],
})

export function copyItems(items: ClipboardItem[]): void {
  state.type = 'copy'
  state.items = items
}

export function cutItems(items: ClipboardItem[]): void {
  state.type = 'cut'
  state.items = items
}

export function clearClipboard(): void {
  state.type = null
  state.items = []
}

export const hasContent = computed(() => state.type !== null && state.items.length > 0)

export const currentClipboardType = computed(() => state.type)

export const currentClipboardItems = computed(() => state.items)

export function isCutItem(id: number): boolean {
  return state.type === 'cut' && state.items.some(i => i.id === id)
}

export function getClipboardIdList(): number[] {
  return state.items.map(i => i.id)
}
