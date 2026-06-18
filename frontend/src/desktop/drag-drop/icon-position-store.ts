import { desktopStateStore, scheduleDesktopStateSave } from '@/desktop/window-manager/desktop-state-store'

export interface IconPosition {
  col?: number
  row?: number
  x: number
  y: number
}

function isValidPosition(value: unknown): value is IconPosition {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.x === 'number' && Number.isFinite(record.x)
    && typeof record.y === 'number' && Number.isFinite(record.y)
}

export function readIconPosition(key: string): IconPosition | null {
  const value = desktopStateStore.state.iconPositions[key]
  return isValidPosition(value) ? value : null
}

export function readIconPositions(): Record<string, IconPosition> {
  return desktopStateStore.state.iconPositions
}

export function updateIconPositions(positions: Record<string, IconPosition>): void {
  Object.entries(positions).forEach(([key, value]) => {
    desktopStateStore.state.iconPositions[key] = value
  })
  scheduleDesktopStateSave()
}
