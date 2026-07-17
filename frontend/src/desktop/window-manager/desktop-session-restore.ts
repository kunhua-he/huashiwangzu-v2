import { getApp } from '@/desktop/app-registry/app-registry'
import type { WindowState } from './window-types'
import type { DesktopWindowSnapshot } from './desktop-session-storage'
import { deduplicateSnapshots } from './desktop-session-storage'
import { clampWindowToWorkArea, getDesktopWorkArea } from '@/desktop/config/desktop-chrome-metrics'

type RestoreOptions = {
  snapshots: DesktopWindowSnapshot[]
  currentRole?: string
  containerWidth: number
  containerHeight: number
  generateId: () => string
  generateZIndex: () => number
}

export function buildRestoreWindowList(opts: RestoreOptions): WindowState[] {
  const deduped = deduplicateSnapshots(opts.snapshots)
  const result: WindowState[] = []
  const workArea = getDesktopWorkArea(opts.containerWidth, opts.containerHeight)
  for (const snap of [...deduped].sort((a, b) => a.zIndex - b.zIndex)) {
    const reg = getApp(snap.appKey)
    if (!reg || reg.windowType === 'background-service') continue
    if (reg.allowedRoles && opts.currentRole && !reg.allowedRoles.includes(opts.currentRole)) continue

    const geometry = clampWindowToWorkArea(snap, workArea, reg.minWidth, reg.minHeight)
    const maximized = Boolean(snap.maximized)
    result.push({
      ...snap,
      id: opts.generateId(),
      title: resolveRestoredWindowTitle(snap.appKey, reg.appName, snap.payload || {}),
      icon: reg.icon,
      x: maximized ? workArea.x : geometry.x,
      y: maximized ? workArea.y : geometry.y,
      width: maximized ? workArea.width : geometry.width,
      height: maximized ? workArea.height : geometry.height,
      zIndex: opts.generateZIndex(),
    })
  }
  if (result.length && !result.some(w => w.isActive && !w.minimized)) {
    const lastWindow = [...result].reverse().find(w => !w.minimized)
    if (lastWindow) lastWindow.isActive = true
  }
  return result
}

function resolveRestoredWindowTitle(appKey: string, defaultTitle: string, payload: Record<string, unknown>): string {
  if (appKey === 'desktop') {
    const folderName = typeof payload.folderName === 'string' ? payload.folderName.trim() : ''
    return folderName ? `${defaultTitle} · ${folderName}` : defaultTitle
  }
  return defaultTitle
}
