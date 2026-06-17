/**
 * 拖拽工具函数 — 网格吸附 + 边界检测
 *
 * 图标是 flex 布局，不设绝对坐标。
 * 拖拽结束后通过 transform 偏移实现视觉落点，
 * 落点坐标存储用于后续持久化。
 */
import { reactive } from 'vue'

const GRID = 48
const ICON_W = 88
const ICON_H = 88
const TASKBAR_H = 48

/** 网格吸附 */
export function snapToGrid(val: number): number {
  return Math.round(val / GRID) * GRID
}

/** 边界钳制 + 网格吸附 */
export function clampIconPosition(x: number, y: number): { x: number; y: number } {
  return {
    x: snapToGrid(Math.max(0, Math.min(x, window.innerWidth - ICON_W))),
    y: snapToGrid(Math.max(0, Math.min(y, window.innerHeight - TASKBAR_H - ICON_H))),
  }
}

/**
 * 拖拽落点坐标覆盖表
 * key: data-selection-key value, for example "file:123"
 * value: 落点 transform 偏移 { x, y }
 *
 * 图标渲染时读取此表，有覆盖则用 transform 偏移，
 * 无覆盖则回到 flex 默认位置。
 */
export const dropOverlay = reactive<Record<string, { x: number; y: number }>>({})

export function setDropOverlay(key: string, x: number, y: number): void {
  dropOverlay[key] = { x, y }
}

export function setDropOverlayBatch(
  primaryKey: string, primaryX: number, primaryY: number,
  allKeys: string[], offsetList: { id: string; dx: number; dy: number }[]
): void {
  allKeys.forEach(key => {
    const offset = offsetList.find(o => o.id === key)
    const { x, y } = clampIconPosition(
      key === primaryKey ? primaryX : primaryX + (offset?.dx ?? 0),
      key === primaryKey ? primaryY : primaryY + (offset?.dy ?? 0)
    )
    dropOverlay[key] = { x, y }
  })
}

export function clearDropOverlay(key: string): void {
  delete dropOverlay[key]
}

export function getDropOverlayStyle(key: string): string {
  const p = dropOverlay[key]
  return p ? `translate(${p.x}px, ${p.y}px)` : ''
}
