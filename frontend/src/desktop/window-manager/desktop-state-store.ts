import { reactive, ref } from 'vue'
import { keepaliveFetch } from '@/shared/api'
import { readDesktopStateRequest, saveDesktopStateRequest } from '@/shared/api/desktop'
import { deduplicateSnapshots, type DesktopWindowSnapshot } from './desktop-session-storage'

export interface DesktopPersistentState {
  version: number
  windows: DesktopWindowSnapshot[]
  appState: Record<string, Record<string, unknown>>
  iconPositions: Record<string, { col?: number; row?: number; x: number; y: number }>
}

const state = reactive<DesktopPersistentState>({ version: 1, windows: [], appState: {}, iconPositions: {} })
const loaded = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | null = null
/** framework_desktop_states.version CAS 游标 */
let serverVersion = 0
/** In-flight save to avoid overlapping CAS races from debounce + pagehide. */
let saveInFlight: Promise<void> | null = null
let saveQueued = false

function sanitizeIconPositions(
  input: unknown,
): Record<string, { col?: number; row?: number; x: number; y: number }> {
  if (!input || typeof input !== 'object') return {}
  const out: Record<string, { col?: number; row?: number; x: number; y: number }> = {}
  for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
    if (!key || !value || typeof value !== 'object') continue
    const rec = value as Record<string, unknown>
    const x = typeof rec.x === 'number' && Number.isFinite(rec.x) ? rec.x : null
    const y = typeof rec.y === 'number' && Number.isFinite(rec.y) ? rec.y : null
    if (x === null || y === null) continue
    const item: { col?: number; row?: number; x: number; y: number } = { x, y }
    if (typeof rec.col === 'number' && Number.isFinite(rec.col)) item.col = rec.col
    if (typeof rec.row === 'number' && Number.isFinite(rec.row)) item.row = rec.row
    out[key] = item
  }
  return out
}

function sanitizeAppState(input: unknown): Record<string, Record<string, unknown>> {
  if (!input || typeof input !== 'object') return {}
  const out: Record<string, Record<string, unknown>> = {}
  for (const [appKey, value] of Object.entries(input as Record<string, unknown>)) {
    if (!appKey || !value || typeof value !== 'object' || Array.isArray(value)) continue
    out[appKey] = { ...(value as Record<string, unknown>) }
  }
  return out
}

function applyEnvelope(envelope: {
  serverVersion: number
  state: Partial<DesktopPersistentState>
}) {
  state.windows = Array.isArray(envelope.state.windows)
    ? deduplicateSnapshots(envelope.state.windows as DesktopWindowSnapshot[])
    : []
  state.appState = sanitizeAppState(envelope.state.appState)
  state.iconPositions = sanitizeIconPositions(envelope.state.iconPositions)
  state.version = envelope.state.version ?? 1
  serverVersion = Number(envelope.serverVersion || 0) || 0
}

export async function loadDesktopState() {
  try {
    const envelope = await readDesktopStateRequest()
    applyEnvelope(envelope)
  } catch {
    serverVersion = 0
  }
  loaded.value = true
  return state
}

/** Write window snapshots without scheduling a network save (pagehide path). */
export function setWindowSnapshot(windows: DesktopWindowSnapshot[]) {
  state.windows = deduplicateSnapshots(windows)
}

export function updateWindowSnapshot(windows: DesktopWindowSnapshot[]) {
  setWindowSnapshot(windows)
  scheduleDesktopStateSave()
}

export function readAppState<T>(appKey: string, stateName: string, defaultValue: T): T {
  return (state.appState[appKey]?.[stateName] as T | undefined) ?? defaultValue
}

export function updateAppState(appKey: string, stateName: string, value: unknown) {
  if (!state.appState[appKey]) state.appState[appKey] = {}
  state.appState[appKey][stateName] = value
  scheduleDesktopStateSave()
}

export function scheduleDesktopStateSave() {
  if (!loaded.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    saveTimer = null
    void saveDesktopStateNow()
  }, 180)
}

function snapshotStateJson(): Record<string, unknown> {
  // Strip content version from CAS body; server owns framework_desktop_states.version.
  const { version: _ignored, ...stateJson } = JSON.parse(JSON.stringify(state)) as DesktopPersistentState
  return stateJson as Record<string, unknown>
}

export async function saveDesktopStateNow() {
  if (!loaded.value) return
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  if (saveInFlight) {
    saveQueued = true
    await saveInFlight
    return
  }

  saveInFlight = (async () => {
    try {
      const expected = serverVersion > 0 ? serverVersion : undefined
      const envelope = await saveDesktopStateRequest(
        JSON.parse(JSON.stringify(state)) as DesktopPersistentState,
        expected,
      )
      serverVersion = Number(envelope.serverVersion || (serverVersion + 1)) || (serverVersion + 1)
      state.version = envelope.state.version ?? serverVersion
    } catch (err: unknown) {
      const msg = String((err as { error?: string; message?: string })?.error
        || (err as { message?: string })?.message
        || err
        || '')
      if (msg.includes('DESKTOP_STATE_CONFLICT') || msg.includes('409') || msg.includes('conflict')) {
        // CAS conflict: reload server truth for version, but keep local live windows
        // so an in-progress session is not wiped by a stale tab.
        try {
          const localWindows = state.windows.slice()
          const localAppState = JSON.parse(JSON.stringify(state.appState)) as DesktopPersistentState['appState']
          const localIcons = { ...state.iconPositions }
          await loadDesktopState()
          // Prefer local live window geometry (this tab is authoritative for open windows).
          state.windows = deduplicateSnapshots(localWindows)
          // Merge appState: local keys win on collision (prefs written in this tab).
          for (const [appKey, bucket] of Object.entries(localAppState)) {
            state.appState[appKey] = { ...(state.appState[appKey] || {}), ...bucket }
          }
          // Icon positions: local overrides server for same keys.
          state.iconPositions = { ...state.iconPositions, ...localIcons }
          // Retry once with fresh serverVersion (no expected if still 0).
          const expected = serverVersion > 0 ? serverVersion : undefined
          try {
            const envelope = await saveDesktopStateRequest(
              JSON.parse(JSON.stringify(state)) as DesktopPersistentState,
              expected,
            )
            serverVersion = Number(envelope.serverVersion || (serverVersion + 1)) || (serverVersion + 1)
            state.version = envelope.state.version ?? serverVersion
          } catch {
            /* leave local state; next debounce/pagehide will retry */
          }
        } catch {
          /* ignore */
        }
      }
    } finally {
      saveInFlight = null
      if (saveQueued) {
        saveQueued = false
        void saveDesktopStateNow()
      }
    }
  })()

  await saveInFlight
}

export function saveDesktopStateWithKeepalive() {
  if (!loaded.value) return
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  // Flush latest windows into state before keepalive (caller should updateWindowSnapshot first when possible).
  const expected = serverVersion > 0 ? serverVersion : undefined
  const body: Record<string, unknown> = { state_json: snapshotStateJson() }
  if (expected !== undefined) body.expected_version = expected
  keepaliveFetch('/desktop/state', body)
}

export const desktopStateStore = { state, loaded }
