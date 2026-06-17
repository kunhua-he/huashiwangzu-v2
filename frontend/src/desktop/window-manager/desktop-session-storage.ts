import type { WindowState } from './window-types'

export type DesktopWindowSnapshot = Omit<WindowState, 'id'>

export function createDesktopWindowSnapshot(windows: WindowState[]): DesktopWindowSnapshot[] {
  return windows.map(({ id: _id, ...rest }) => rest)
}
