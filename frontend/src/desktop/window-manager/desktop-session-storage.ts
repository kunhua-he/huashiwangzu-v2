import type { WindowState } from './window-types'

export type DesktopWindowSnapshot = Omit<WindowState, 'id'>

export const MAX_WINDOWS = 30

/** Product `files` + legacy alias `desktop` are the same Finder shell. */
export function isFinderAppKey(appKey: string | undefined | null): boolean {
  return appKey === 'desktop' || appKey === 'files'
}

/** Root folder is 0 / null / undefined / '' — normalize for dedupe keys. */
export function normalizeFinderFolderId(payload?: Record<string, unknown> | null): string {
  const raw = payload?.folderId
  if (raw === null || raw === undefined || raw === '' || raw === 0 || raw === '0') return '0'
  return String(raw)
}

function asFiniteNumber(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : fallback
}

function sanitizePayload(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return {}
  return { ...(payload as Record<string, unknown>) }
}

function sanitizePreMaximizeState(
  value: unknown,
): { x: number; y: number; width: number; height: number } | undefined {
  if (!value || typeof value !== 'object') return undefined
  const rec = value as Record<string, unknown>
  const width = asFiniteNumber(rec.width, 0)
  const height = asFiniteNumber(rec.height, 0)
  if (width <= 0 || height <= 0) return undefined
  return {
    x: asFiniteNumber(rec.x, 0),
    y: asFiniteNumber(rec.y, 0),
    width,
    height,
  }
}

/** Drop one-shot fields and coerce snapshot shape before persist/restore. */
export function sanitizeWindowSnapshot(snap: DesktopWindowSnapshot): DesktopWindowSnapshot {
  const payload = sanitizePayload(snap.payload)
  const preMaximizeState = sanitizePreMaximizeState(snap.preMaximizeState)
  const maximized = Boolean(snap.maximized)
  return {
    appKey: String(snap.appKey || ''),
    title: String(snap.title || ''),
    icon: String(snap.icon || ''),
    x: asFiniteNumber(snap.x, 0),
    y: asFiniteNumber(snap.y, 0),
    width: Math.max(1, asFiniteNumber(snap.width, 640)),
    height: Math.max(1, asFiniteNumber(snap.height, 480)),
    zIndex: asFiniteNumber(snap.zIndex, 100),
    minimized: Boolean(snap.minimized),
    maximized,
    isActive: Boolean(snap.isActive),
    payload,
    preMaximizeState,
    windowType: snap.windowType ? String(snap.windowType) : undefined,
    // animationOrigin is one-shot open animation — never persist
  }
}

export function deduplicateSnapshots(snapshots: DesktopWindowSnapshot[]): DesktopWindowSnapshot[] {
  const finderWindows = new Map<string, DesktopWindowSnapshot>()
  const multiWindows: DesktopWindowSnapshot[] = []

  for (const raw of snapshots) {
    if (!raw || typeof raw !== 'object') continue
    const snap = sanitizeWindowSnapshot(raw)
    if (!snap.appKey) continue

    if (isFinderAppKey(snap.appKey)) {
      // Canonicalize persisted Finder key so old `desktop` and new `files` merge.
      const normalized: DesktopWindowSnapshot = { ...snap, appKey: 'desktop' }
      const key = `finder::${normalizeFinderFolderId(normalized.payload)}`
      const existing = finderWindows.get(key)
      if (!existing || normalized.zIndex > existing.zIndex) {
        finderWindows.set(key, normalized)
      }
      continue
    }

    // allowMultiple is unknown here; keep all non-finder and let restore filter by registry.
    multiWindows.push(snap)
  }

  // Prefer stable order: non-finder then finder, both sorted by zIndex.
  const combined = [...multiWindows, ...finderWindows.values()]
    .sort((a, b) => a.zIndex - b.zIndex)
  return combined.slice(0, MAX_WINDOWS)
}

export function createDesktopWindowSnapshot(windows: WindowState[]): DesktopWindowSnapshot[] {
  return deduplicateSnapshots(
    windows.map(({ id: _id, animationOrigin: _origin, ...rest }) => sanitizeWindowSnapshot(rest)),
  )
}
