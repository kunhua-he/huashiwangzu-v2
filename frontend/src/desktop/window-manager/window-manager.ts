import { reactive, computed, ref, watch } from 'vue'
import type { WindowState, TaskbarItem } from '@/desktop/window-manager/window-types'
import { getApp } from '@/desktop/app-registry/app-registry'
import { useUserStore } from '@/platform/stores/user'
import type { DesktopWindowSnapshot } from './desktop-session-storage'
import { buildRestoreWindowList } from './desktop-session-restore'

const windows = reactive<WindowState[]>([])
let nextZIndex = 100
let nextId = 1
const desktopContainerSize = reactive({ width: window.innerWidth, height: window.innerHeight })

function generateId(): string { return `win_${Date.now()}_${nextId++}` }

function generateZIndex(): number { return nextZIndex++ }

const taskbarItems = ref<TaskbarItem[]>([])
watch(() => windows.map(w => ({
  id: w.id, title: w.title, icon: w.icon,
  isActive: w.isActive, minimized: w.minimized,
})), (value) => { taskbarItems.value = value }, { immediate: true, deep: true })

function openWindow(appKey: string, payload?: unknown): string | null {
  const app = getApp(appKey)
  if (!app) return null
  const store = useUserStore()
  const currentRole = store.userInfo?.role?.toLowerCase()
  if (app.allowedRoles && currentRole && !app.allowedRoles.includes(currentRole)) {
    console.warn(`打开窗口被拒绝：角色 ${currentRole} 无权访问应用 ${appKey}`)
    return null
  }

  if (app.windowType === '后台服务') {
    const existingService = windows.find(w => w.appKey === appKey)
    if (existingService) { activateWindow(existingService.id); return existingService.id }
    console.warn(`后台服务 ${appKey} 不支持窗口模式`)
    return null
  }

  if (!app.allowMultiple) {
    const existingWindow = windows.find(w => w.appKey === appKey)
    if (existingWindow) { activateWindow(existingWindow.id); existingWindow.minimized = false; return existingWindow.id }
  }

  const offset = (windows.length % 10) * 30
  const id = generateId()

  windows.push({
    id, appKey,
    title: app.appName, icon: app.icon,
    x: app.defaultWidth > 800 ? 120 + offset : 160 + offset,
    y: 110 + offset,
    width: app.defaultWidth, height: app.defaultHeight,
    zIndex: nextZIndex++,
    minimized: false, maximized: false, isActive: true,
     windowType: app.windowType || '普通窗口',
     payload: (payload ?? {}) as Record<string, unknown>,
  })

  windows.forEach(w => { if (w.id !== id) w.isActive = false })
  return id
}

function closeWindow(id: string) {
  const idx = windows.findIndex(w => w.id === id)
  if (idx === -1) return
  windows.splice(idx, 1)
}

function toggleMinimized(id: string) {
  const w = windows.find(x => x.id === id)
  if (!w) return
  w.minimized = !w.minimized
  if (w.minimized) {
    w.isActive = false
    const next = [...windows].reverse().find(x => !x.minimized)
    if (next) { next.isActive = true }
  } else { activateWindow(id) }
}

function toggleMaximized(id: string) {
  const w = windows.find(x => x.id === id)
  if (!w) return
  if (w.maximized) {
    if (w.preMaximizeState) { w.x = w.preMaximizeState.x; w.y = w.preMaximizeState.y; w.width = w.preMaximizeState.width; w.height = w.preMaximizeState.height }
    w.maximized = false
  } else {
    w.preMaximizeState = { x: w.x, y: w.y, width: w.width, height: w.height }
    w.x = 0; w.y = 0
    w.width = desktopContainerSize.width
    w.height = desktopContainerSize.height - 48
    w.maximized = true
  }
}

function activateWindow(id: string) {
  const w = windows.find(x => x.id === id)
  if (!w) return
  windows.forEach(x => x.isActive = false)
  w.isActive = true; w.zIndex = nextZIndex++; w.minimized = false
}

function setContainerSize(width: number, height: number) {
  desktopContainerSize.width = width
  desktopContainerSize.height = height
}

function updateWindowPosition(id: string, x: number, y: number) {
  const w = windows.find(win => win.id === id)
  if (!w || w.maximized) return
  w.x = x
  w.y = y
}

function updateWindowSize(id: string, width: number, height: number) {
  const w = windows.find(win => win.id === id)
  if (w && !w.maximized) { w.width = width; w.height = height }
}

function updateWindowGeometry(id: string, x: number, y: number, width: number, height: number) {
  const w = windows.find(win => win.id === id)
  if (w && !w.maximized) { w.x = x; w.y = y; w.width = width; w.height = height }
}

function restoreWindows(snapshot: DesktopWindowSnapshot[], currentRole?: string) {
  const restoredWindows = buildRestoreWindowList({
    快照: snapshot, 当前角色: currentRole,
    容器宽: desktopContainerSize.width,
    容器高: desktopContainerSize.height,
    生成id: generateId, 生成层级: generateZIndex,
  })
  for (const w of restoredWindows) {
    const existingWindow = windows.find(x => x.appKey === w.appKey && x.minimized === w.minimized)
    if (existingWindow) { activateWindow(existingWindow.id); continue }
    windows.push(w)
  }
}

export function useWindowManager() {
  return {
    windows,
    openedWindowCount: computed(() => windows.length),
    taskbarItems,
    openWindow, closeWindow, toggleMinimized, toggleMaximized, activateWindow,
    updateWindowPosition, updateWindowSize, updateWindowGeometry,
    setContainerSize, restoreWindows,
  }
}

export const windowManager = {
  windows,
  get openedWindowCount() { return windows.length },
  taskbarItems,
  openWindow, closeWindow, toggleMinimized, toggleMaximized, activateWindow,
  updateWindowPosition, updateWindowSize, updateWindowGeometry,
  setContainerSize, restoreWindows,
}
