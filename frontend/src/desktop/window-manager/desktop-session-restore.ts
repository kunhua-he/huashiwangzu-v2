import { getApp } from '@/desktop/app-registry/app-registry'
import type { WindowState } from './window-types'
import {
  deduplicateSnapshots,
  isFinderAppKey,
  type DesktopWindowSnapshot,
} from './desktop-session-storage'
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
  const singletonKeys = new Set<string>()

  // Fallback when container not laid out yet (0×0) — avoid clamping everything to zero.
  const safeWidth = opts.containerWidth > 0 ? opts.containerWidth : (typeof window !== 'undefined' ? window.innerWidth : 1280)
  const safeHeight = opts.containerHeight > 0 ? opts.containerHeight : (typeof window !== 'undefined' ? window.innerHeight : 800)
  const effectiveWorkArea = (opts.containerWidth > 0 && opts.containerHeight > 0)
    ? workArea
    : getDesktopWorkArea(safeWidth, safeHeight)

  for (const snap of [...deduped].sort((a, b) => a.zIndex - b.zIndex)) {
    const reg = getApp(snap.appKey) || (isFinderAppKey(snap.appKey) ? (getApp('files') || getApp('desktop')) : undefined)
    if (!reg || reg.windowType === 'background-service') continue
    if (reg.allowedRoles && opts.currentRole && !reg.allowedRoles.includes(opts.currentRole)) continue

    const canonicalKey = reg.canonicalAppKey || reg.appKey
    if (!reg.allowMultiple && singletonKeys.has(canonicalKey)) continue
    if (!reg.allowMultiple) singletonKeys.add(canonicalKey)

    // Persist Finder under desktop key for open-path compatibility with existing shell handlers.
    const appKey = isFinderAppKey(snap.appKey) ? (getApp('desktop') ? 'desktop' : reg.appKey) : snap.appKey
    const geometry = clampWindowToWorkArea(snap, effectiveWorkArea, reg.minWidth, reg.minHeight)
    const maximized = Boolean(snap.maximized)
    const preMaximizeState = snap.preMaximizeState
      ? clampWindowToWorkArea(snap.preMaximizeState, effectiveWorkArea, reg.minWidth, reg.minHeight)
      : undefined

    const restoredGeometry = maximized
      ? { x: effectiveWorkArea.x, y: effectiveWorkArea.y, width: effectiveWorkArea.width, height: effectiveWorkArea.height }
      : avoidRestoredOverlap(geometry, result, effectiveWorkArea, reg.minWidth, reg.minHeight)

    result.push({
      ...snap,
      appKey,
      id: opts.generateId(),
      title: resolveRestoredWindowTitle(appKey, reg.appName, snap.payload || {}),
      icon: reg.icon,
      x: restoredGeometry.x,
      y: restoredGeometry.y,
      width: restoredGeometry.width,
      height: restoredGeometry.height,
      zIndex: opts.generateZIndex(),
      minimized: Boolean(snap.minimized),
      maximized,
      isActive: Boolean(snap.isActive),
      preMaximizeState,
      windowType: reg.windowType || snap.windowType || 'normal',
      payload: snap.payload || {},
    })
  }

  // Exactly one active non-minimized window when possible.
  if (result.length) {
    const visible = result.filter(w => !w.minimized)
    if (visible.length) {
      const preferred = [...visible].reverse().find(w => w.isActive) || [...visible].sort((a, b) => b.zIndex - a.zIndex)[0]
      for (const w of result) w.isActive = w.id === preferred.id
    } else {
      for (const w of result) w.isActive = false
    }
  }
  return result
}

function avoidRestoredOverlap(
  geometry: ReturnType<typeof clampWindowToWorkArea>,
  restored: WindowState[],
  workArea: ReturnType<typeof getDesktopWorkArea>,
  minWidth: number,
  minHeight: number,
) {
  let candidate = geometry
  for (let attempt = 0; attempt < restored.length + 1; attempt += 1) {
    const overlaps = restored.some((window) =>
      !window.minimized
      && window.x === candidate.x
      && window.y === candidate.y
      && window.width === candidate.width
      && window.height === candidate.height,
    )
    if (!overlaps) return candidate
    candidate = clampWindowToWorkArea({
      ...candidate,
      x: candidate.x + 28,
      y: candidate.y + 28,
    }, workArea, minWidth, minHeight)
  }
  return candidate
}

function resolveRestoredWindowTitle(appKey: string, defaultTitle: string, payload: Record<string, unknown>): string {
  if (isFinderAppKey(appKey)) {
    const folderName = typeof payload.folderName === 'string' ? payload.folderName.trim() : ''
    if (folderName && folderName !== '桌面' && folderName !== defaultTitle) return folderName
    return defaultTitle || '文件'
  }
  return defaultTitle
}
