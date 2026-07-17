export const DESKTOP_MENU_BAR_HEIGHT = 24
export const DESKTOP_DOCK_ICON_SIZE = 48
export const DESKTOP_DOCK_PADDING = 7
export const DESKTOP_DOCK_HEIGHT = DESKTOP_DOCK_ICON_SIZE + DESKTOP_DOCK_PADDING * 2
export const DESKTOP_DOCK_BOTTOM_GAP = 10
export const DESKTOP_WINDOW_EDGE_GAP = 8

export interface DesktopWorkArea {
  x: number
  y: number
  width: number
  height: number
}

export interface DesktopWindowGeometry {
  x: number
  y: number
  width: number
  height: number
}

export function getDesktopWorkArea(containerWidth: number, containerHeight: number): DesktopWorkArea {
  const width = Math.max(0, containerWidth)
  const dockTop = Math.max(
    DESKTOP_MENU_BAR_HEIGHT,
    containerHeight - DESKTOP_DOCK_HEIGHT - DESKTOP_DOCK_BOTTOM_GAP,
  )
  const bottom = Math.max(DESKTOP_MENU_BAR_HEIGHT, dockTop - DESKTOP_WINDOW_EDGE_GAP)
  return {
    x: 0,
    y: DESKTOP_MENU_BAR_HEIGHT,
    width,
    height: Math.max(0, bottom - DESKTOP_MENU_BAR_HEIGHT),
  }
}

export function clampWindowToWorkArea(
  geometry: DesktopWindowGeometry,
  workArea: DesktopWorkArea,
  minWidth = 1,
  minHeight = 1,
): DesktopWindowGeometry {
  const width = Math.min(Math.max(Math.min(minWidth, workArea.width), geometry.width), workArea.width)
  const height = Math.min(Math.max(Math.min(minHeight, workArea.height), geometry.height), workArea.height)
  const maxX = workArea.x + Math.max(0, workArea.width - width)
  const maxY = workArea.y + Math.max(0, workArea.height - height)
  return {
    x: Math.round(Math.max(workArea.x, Math.min(geometry.x, maxX))),
    y: Math.round(Math.max(workArea.y, Math.min(geometry.y, maxY))),
    width: Math.round(width),
    height: Math.round(height),
  }
}
