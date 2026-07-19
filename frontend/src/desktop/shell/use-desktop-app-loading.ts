import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { loadAppRegistry } from '@/desktop/app-registry/app-loader'
import { useWindowManager } from '@/desktop/window-manager/window-manager'
import { loadDesktopState } from '@/desktop/window-manager/desktop-state-store'
import { createWindowStateSync } from '@/desktop/window-manager/window-state-sync'
import { restorePersistedIconPositions } from '@/desktop/drag-drop/drag-tool'
import { useUserStore } from '@/platform/stores/user'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import type { Ref } from 'vue'
import { isLauncherVisibleApp } from '@/desktop/app-registry/app-visibility'

export function useDesktopAppLoading(currentRole: Ref<string>) {
  const windowMgr = useWindowManager()
  const userStore = useUserStore()
  const allAppList = ref<AppRegistryEntry[]>([])
  const desktopAppList = ref<AppRegistryEntry[]>([])
  const launcherAppList = ref<AppRegistryEntry[]>([])
  const sidebarAppList = ref<AppRegistryEntry[]>([])
  const trayAppList = ref<AppRegistryEntry[]>([])
  const registryError = ref<string | null>(null)
  const loading = ref(true)
  const desktopContainerRef = ref<HTMLElement | null>(null)
  let resizeObserver: ResizeObserver | null = null
  let iconRestoreRaf = 0
  let restoredOnce = false

  function runtimePermissions(role?: string): string[] {
    if (role === 'admin') return ['viewer', 'editor', 'admin']
    if (role === 'editor') return ['viewer', 'editor']
    return ['viewer']
  }

  const windowSync = createWindowStateSync(windowMgr.windows)

  function scheduleIconRestore() {
    if (iconRestoreRaf) cancelAnimationFrame(iconRestoreRaf)
    iconRestoreRaf = requestAnimationFrame(() => {
      iconRestoreRaf = 0
      restorePersistedIconPositions()
      // Second frame: icon DOM may still be mounting after file list arrives.
      requestAnimationFrame(() => restorePersistedIconPositions())
    })
  }

  function updateContainerSize() {
    const el = desktopContainerRef.value
    if (el) {
      const width = el.clientWidth || window.innerWidth
      const height = el.clientHeight || window.innerHeight
      windowMgr.setContainerSize(width, height)
    }
    scheduleIconRestore()
  }

  async function restoreDesktopSession() {
    if (!userStore.userInfo?.id || restoredOnce) return
    // Measure container before restore so maximized/clamp use real work area.
    updateContainerSize()
    const desktopState = await loadDesktopState()
    // Re-measure after await — layout may have settled.
    updateContainerSize()
    windowMgr.restoreWindows(desktopState.windows, currentRole.value)
    restoredOnce = true
    await nextTick()
    updateContainerSize()
    scheduleIconRestore()
  }

  async function loadAppRegistryData() {
    registryError.value = null
    loading.value = true
    restoredOnce = false
    try {
      const allApps = await loadAppRegistry(currentRole.value)
      const byOrder = (a: AppRegistryEntry, b: AppRegistryEntry) =>
        (a.sortOrder ?? 100) - (b.sortOrder ?? 100) || a.appName.localeCompare(b.appName)
      const ordered = [...allApps].sort(byOrder)
      allAppList.value = ordered
      desktopAppList.value = ordered.filter(a => a.showOnDesktop)
      launcherAppList.value = ordered.filter(isLauncherVisibleApp)
      sidebarAppList.value = ordered.filter(a => a.showInSidebar)
      trayAppList.value = ordered.filter(a => a.showInTray)

      // 给模块 runtime 注入框架上下文（当前用户权限等）
      ;(window as unknown as { __HUASHI_RUNTIME__?: unknown }).__HUASHI_RUNTIME__ = {
        mode: 'framework',
        api_base_url: '/api',
        permissions: runtimePermissions(userStore.userInfo?.role),
        module_settings: {},
      }

      await restoreDesktopSession()

      resizeObserver?.disconnect()
      resizeObserver = new ResizeObserver(updateContainerSize)
      if (desktopContainerRef.value) resizeObserver.observe(desktopContainerRef.value)
      else {
        // Container ref may not be ready on first mount race — observe next tick.
        await nextTick()
        if (desktopContainerRef.value) resizeObserver.observe(desktopContainerRef.value)
      }
    } catch (e: unknown) {
      registryError.value = (e as {message?: string})?.message || '桌面应用清单加载失败，请联系管理员'
    } finally {
      loading.value = false
      if (import.meta.env.DEV) {
        const { useDesktopAppHandleV2 } = await import('@/desktop/app-registry/desktop-app-handle-v2')
        const handleV2 = useDesktopAppHandleV2()
        ;(window as { __test__?: unknown }).__test__ = { handleV2 }
      }
    }
  }

  function retryLoadRegistry() { loadAppRegistryData() }

  onMounted(loadAppRegistryData)
  onUnmounted(() => {
    if (iconRestoreRaf) cancelAnimationFrame(iconRestoreRaf)
    windowSync.stopSync()
    resizeObserver?.disconnect()
  })

  return {
    allAppList,
    desktopAppList,
    launcherAppList,
    sidebarAppList,
    trayAppList,
    registryError,
    loading,
    desktopContainerRef,
    retryLoadRegistry,
    updateContainerSize,
  }
}
