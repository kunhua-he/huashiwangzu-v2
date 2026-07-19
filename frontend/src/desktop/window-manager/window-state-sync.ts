import { ref, watch, type Reactive } from 'vue'
import type { TaskbarItem, WindowState } from './window-types'
import { createDesktopWindowSnapshot } from './desktop-session-storage'
import {
  saveDesktopStateNow,
  saveDesktopStateWithKeepalive,
  setWindowSnapshot,
  updateWindowSnapshot,
} from './desktop-state-store'

export function createWindowStateSync(windows: Reactive<WindowState[]>) {
  const taskbarItems = ref<TaskbarItem[]>([])

  function flushSnapshot(schedule = true) {
    const snap = createDesktopWindowSnapshot(windows)
    if (schedule) updateWindowSnapshot(snap)
    else setWindowSnapshot(snap)
  }

  function saveNow() {
    flushSnapshot(true)
    void saveDesktopStateNow()
  }

  function saveKeepalive() {
    // Ensure latest geometry is in store before pagehide keepalive POST.
    // Do not schedule a debounced save that would race the keepalive body.
    flushSnapshot(false)
    saveDesktopStateWithKeepalive()
  }

  const stopTaskbarSync = watch(() => windows.map((w: WindowState) => ({
    id: w.id, title: w.title, icon: w.icon,
    isActive: w.isActive, minimized: w.minimized, appKey: w.appKey,
  })), value => { taskbarItems.value = value }, { immediate: true, deep: true })

  let sessionSyncTimer: ReturnType<typeof setTimeout> | null = null
  const stopSessionSync = watch(windows, () => {
    if (sessionSyncTimer) clearTimeout(sessionSyncTimer)
    sessionSyncTimer = setTimeout(() => {
      sessionSyncTimer = null
      flushSnapshot(true)
    }, 300)
  }, { deep: true })

  function onVisibilityChange() {
    if (document.visibilityState === 'hidden') {
      // Mobile Safari / tab switch: pagehide may lag; flush keepalive early.
      saveKeepalive()
    }
  }

  window.addEventListener('pagehide', saveKeepalive)
  window.addEventListener('beforeunload', saveKeepalive)
  document.addEventListener('visibilitychange', onVisibilityChange)

  function stopSync() {
    if (sessionSyncTimer) { clearTimeout(sessionSyncTimer); sessionSyncTimer = null }
    saveNow()
    stopTaskbarSync()
    stopSessionSync()
    window.removeEventListener('pagehide', saveKeepalive)
    window.removeEventListener('beforeunload', saveKeepalive)
    document.removeEventListener('visibilitychange', onVisibilityChange)
  }

  return {
    taskbarItems,
    saveNow,
    stopSync,
  }
}
