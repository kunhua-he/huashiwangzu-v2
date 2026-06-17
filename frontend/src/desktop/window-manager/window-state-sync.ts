import { ref, watch, type Reactive } from 'vue'
import type { TaskbarItem, WindowState } from './window-types'
import { createDesktopWindowSnapshot } from './desktop-session-storage'
import { saveDesktopStateNow, saveDesktopStateWithKeepalive, updateWindowSnapshot } from './desktop-state-store'

export function createWindowStateSync(windows: Reactive<WindowState[]>) {
  const taskbarItems = ref<TaskbarItem[]>([])
  function saveNow() {
    updateWindowSnapshot(createDesktopWindowSnapshot(windows))
    void saveDesktopStateNow()
  }

  const stopTaskbarSync = watch(() => windows.map((w: WindowState) => ({
    id: w.id, title: w.title, icon: w.icon,
    isActive: w.isActive, minimized: w.minimized,
  })), value => { taskbarItems.value = value }, { immediate: true, deep: true })

  const stopSessionSync = watch(windows, () => {
    updateWindowSnapshot(createDesktopWindowSnapshot(windows))
  }, { deep: true })

  window.addEventListener('pagehide', saveDesktopStateWithKeepalive)

  function stopSync() {
    saveNow()
    stopTaskbarSync()
    stopSessionSync()
    window.removeEventListener('pagehide', saveDesktopStateWithKeepalive)
  }

  return {
    taskbarItems,
    saveNow,
    stopSync,
  }
}
