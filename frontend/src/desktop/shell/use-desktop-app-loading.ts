import { ref, onMounted, onUnmounted } from 'vue'
import { loadAppRegistry } from '@/desktop/app-registry/app-loader'
import { useWindowManager } from '@/desktop/window-manager/window-manager'
import { loadDesktopState } from '@/desktop/window-manager/desktop-state-store'
import { createWindowStateSync } from '@/desktop/window-manager/window-state-sync'
import { useUserStore } from '@/platform/stores/user'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import type { Ref } from 'vue'

export function useDesktopAppLoading(当前角色: Ref<string>) {
  const 管理器 = useWindowManager()
  const 用户Store = useUserStore()
  const 桌面应用列表 = ref<AppRegistryEntry[]>([])
  const 开始菜单应用列表 = ref<AppRegistryEntry[]>([])
  const 右侧功能应用列表 = ref<AppRegistryEntry[]>([])
  const 托盘应用列表 = ref<AppRegistryEntry[]>([])
  const 注册表错误 = ref<string | null>(null)
  const 加载中 = ref(true)
  const 桌面容器引用 = ref<HTMLElement | null>(null)
  let 尺寸观察器: ResizeObserver | null = null

  const 窗口同步 = createWindowStateSync(管理器.windows)

  function 更新容器尺寸() {
    if (桌面容器引用.value) 管理器.setContainerSize(桌面容器引用.value.clientWidth, 桌面容器引用.value.clientHeight)
  }

  async function 加载应用注册表() {
    注册表错误.value = null
    加载中.value = true
    try {
      const 全部应用 = await loadAppRegistry(当前角色.value)
      桌面应用列表.value = 全部应用.filter(a => a.showOnDesktop)
      开始菜单应用列表.value = 全部应用.filter(a => a.showInLauncher)
      右侧功能应用列表.value = 全部应用.filter(a => a.showInSidebar)
      托盘应用列表.value = 全部应用.filter(a => a.showInTray)

      if (用户Store.userInfo?.userId) {
        const 桌面状态 = await loadDesktopState()
        管理器.restoreWindows(桌面状态.windows, 当前角色.value)
      }

      更新容器尺寸()
      尺寸观察器 = new ResizeObserver(更新容器尺寸)
      if (桌面容器引用.value) 尺寸观察器.observe(桌面容器引用.value)
    } catch (e: unknown) {
      注册表错误.value = (e as {message?: string})?.message || '桌面应用清单加载失败，请联系管理员'
    } finally {
      加载中.value = false
      if (import.meta.env.DEV) {
        const { useDesktopAppHandleV2 } = await import('@/desktop/app-registry/desktop-app-handle-v2')
        const 句柄V2 = useDesktopAppHandleV2()
        ;(window as { __test__?: unknown }).__test__ = { 句柄V2 }
      }
    }
  }

  function 重试加载注册表() { 加载应用注册表() }

  onMounted(加载应用注册表)
  onUnmounted(() => {
    窗口同步.stopSync()
    尺寸观察器?.disconnect()
  })

  return {
    桌面应用列表, 开始菜单应用列表, 右侧功能应用列表, 托盘应用列表,
    注册表错误, 加载中, 桌面容器引用, 重试加载注册表, 更新容器尺寸,
  }
}
