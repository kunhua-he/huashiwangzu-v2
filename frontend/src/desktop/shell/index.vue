<template>
  <div ref="desktopContainerRef" class="desktop-shell-container" @contextmenu.prevent="handleDesktopContextMenu" @mousedown="handleDesktopMouseDown" @dragover.prevent="onDragEnter" @dragleave.prevent="onDragLeave" @drop.prevent="onDrop">
    <div class="desktop-shell-wallpaper" :style="{ backgroundImage: `url(${wallpaper})` }" />
    <div class="desktop-shell-icon-layer">
      <component :is="desktopIconGrid" :app-list="desktopAppList" :file-list="desktopFileList" @openApp="handleOpenApp" @openFile="openDesktopEntry" @app-context-menu="handleAppContextMenu" />
      <SelectionBox />
    </div>
    <component
      :is="desktopWindowFrame"
      v-for="w in 管理器.windows"
      :key="w.id"
      :id="w.id"
      :title="w.title"
      :icon="w.icon"
      :x="w.x"
      :y="w.y"
      :width="w.width"
      :height="w.height"
      :z-index="w.zIndex"
      :minimized="w.minimized"
      :maximized="w.maximized"
      :is-active="w.isActive"
      :app-key="w.appKey"
      :payload="w.payload"
      @activate="管理器.activateWindow"
      @close="管理器.closeWindow"
      @minimize="管理器.toggleMinimized"
      @maximize="管理器.toggleMaximized"
      @update-position="管理器.updateWindowPosition"
      @update-geometry="管理器.updateWindowGeometry"
    />
    <component :is="desktopTaskbar" :items="unref(管理器.taskbarItems)" :launcher-open="showLauncher" :tray-apps="trayAppList" @switchWindow="handleSwitchWindow" @openLauncher="showLauncher = !showLauncher" @openTrayApp="管理器.openWindow" />
    <component :is="desktopLauncher" v-if="showLauncher" :show="showLauncher" :app-list="launcherAppList" @openApp="handleLauncherOpen" @execute-command="handleLauncherCommand" @close="showLauncher = false" />
    <component :is="desktopRightSidebar" :show="showRightSidebar" :current-path="rightSidebarPath" :current-app-key="rightSidebarAppKey" :app-list="sidebarAppList" @close="showRightSidebar = false" @switch="openSidebar" @open-window="handleOpenApp" />
    <ContextMenu
      :visible="contextMenu.visible.value"
      :x="contextMenu.x.value"
      :y="contextMenu.y.value"
      :context-type="contextMenu.context.value?.type"
      :current-items="contextMenu.currentItems.value"
      :active-submenu="contextMenu.activeSubmenu.value"
      :open-submenu="contextMenu.openSubmenu"
      :close-submenu="contextMenu.closeSubmenu"
      :keep-submenu-open="contextMenu.keepSubmenuOpen"
      @select="handleContextMenuSelect"
    />
    <div v-if="registryError" class="desktop-shell-error">
       <p>{{ registryError }}</p>
       <button @click="retryLoadRegistry">重试</button>
     </div>
     <div v-else-if="!管理器.openedWindowCount" class="desktop-shell-hint">
       双击图标openApp · 右键继续管理文件与回收站
     </div>
     <div v-if="isDragActive" class="desktop-shell-drop-hint">松开后上传到桌面</div>
     <div v-if="loading" class="desktop-shell-loading">加载中...</div>
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref, computed, unref } from 'vue'
import { useContextMenu } from '@/desktop/context-menu/use-context-menu'
import ContextMenu from '@/desktop/context-menu/context-menu.vue'
import { useWindowManager } from '@/desktop/window-manager/window-manager'
import { getApp } from '@/desktop/app-registry/app-registry'
import { usePermission } from '@/shared/composables/use-permission'
import { useUserStore } from '@/platform/stores/user'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import SelectionBox from '@/desktop/selection/SelectionBox.vue'
import { useDesktopShellDropUpload } from './use-desktop-shell-drop-upload'
import { useDesktopRootFiles } from './use-desktop-root-files'
import { useDesktopAppLoading } from './use-desktop-app-loading'
import { useDesktopPointer } from './use-desktop-pointer'
const desktopIconGrid = defineAsyncComponent(() => import('@/desktop/shell/desktop-icon-grid.vue'))
const desktopWindowFrame = defineAsyncComponent(() => import('@/desktop/window-manager/desktop-window-frame.vue'))
const desktopTaskbar = defineAsyncComponent(() => import('@/desktop/taskbar/desktop-taskbar.vue'))
const desktopLauncher = defineAsyncComponent(() => import('@/desktop/launcher/desktop-launcher.vue'))
const desktopRightSidebar = defineAsyncComponent(() => import('@/desktop/shell/desktop-right-sidebar.vue'))
const 管理器 = useWindowManager()
const { isEditorOrAbove: canBusinessWrite, currentRole } = usePermission()
const contextMenu = useContextMenu()
const 用户Store = useUserStore()
const { emit } = useDesktopEventBus()
const { isDragActive, onDragEnter, onDragLeave, onDrop } = useDesktopShellDropUpload()
const { desktopFileList, openDesktopEntry } = useDesktopRootFiles()
const { desktopAppList, launcherAppList, sidebarAppList, trayAppList, registryError, loading, desktopContainerRef, retryLoadRegistry, updateContainerSize } = useDesktopAppLoading(currentRole)
const { handleDesktopMouseDown } = useDesktopPointer()

const showLauncher = ref(false); const showRightSidebar = ref(false); const rightSidebarAppKey = ref('dashboard')

const wallpaper = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0f172a"/><stop offset="50%" stop-color="#1d4ed8"/><stop offset="100%" stop-color="#7c3aed"/></linearGradient><radialGradient id="r" cx="30%" cy="20%" r="60%"><stop offset="0%" stop-color="rgba(191,219,254,0.35)"/><stop offset="100%" stop-color="rgba(15,23,42,0)"/></radialGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><rect width="100%" height="100%" fill="url(#r)"/></svg>')
function handleOpenApp(appKey: string) { 管理器.openWindow(appKey) }
function openSidebar(appKey = 'dashboard') { rightSidebarAppKey.value = appKey; showRightSidebar.value = true }
function handleLauncherOpen(appKey: string) {
  showLauncher.value = false
  const app = getApp(appKey)
  if (app?.showInSidebar) openSidebar(appKey); else handleOpenApp(appKey)
}
async function handleLauncherCommand(command: string) {
  const { windows: ws, toggleMinimized: toggle } = 管理器
  if (command === 'open-sidebar') openSidebar('dashboard')
  else if (command === 'refresh-desktop') updateContainerSize()
  else if (command === 'logout') { await 用户Store.logout(); window.location.href = '/' }
  else if (command === 'minimize-all' || command === 'restore-all') ws.forEach((w: { id: string }) => toggle(w.id))
  showLauncher.value = false
}
function getSidebarPath(appKey: string): string {
  const app = sidebarAppList.value.find(a => a.appKey === appKey)
  return app ? '/' + app.appKey : '/dashboard'
}
const rightSidebarPath = computed(() => getSidebarPath(rightSidebarAppKey.value))
function handleAppContextMenu(appKey: string, e: MouseEvent) {
  const items = contextMenu.createDesktopShellIconMenu(appKey, canBusinessWrite.value)
  if (!items.length) return
  contextMenu.open(e, items, { type: 'desktop-shell-icon', target: { appKey } })
}
function handleDesktopContextMenu(e: MouseEvent) {
  const el = e.target as HTMLElement
  if (el.closest('.desktop-window') || el.closest('.file-list-area')) return
  contextMenu.open(e, contextMenu.createDesktopShellBlankMenu(), { type: 'desktop-shell-blank' })
}

function handleContextMenuSelect(键: string) {
  contextMenu.close()
  const menuContext = contextMenu.context.value
  const appKey = (menuContext?.target?.appKey as string) || ''

  // 全局动作
  if (键 === 'refresh-desktop') { updateContainerSize(); return }
  if (键 === 'open-start-menu') { showLauncher.value = true; return }
  if (键 === 'upload-file') { 管理器.openWindow('desktop'); emit('desktop:upload-file', { folderId: null }); return }
  if (键 === 'create-folder') { 管理器.openWindow('desktop'); emit('desktop:create-folder', { folderId: null }); return }
  if (键 === 'open-file-manager') { 管理器.openWindow('desktop'); return }
  if (键 === 'open-recycle-bin') { 管理器.openWindow('recycle'); return }

  if (键 === 'open-app' && appKey) { 管理器.openWindow(appKey); return }
}
function handleSwitchWindow(id: string) {
  const w = 管理器.windows.find(x => x.id === id)
  if (w) {
    if (w.minimized || !w.isActive) { 管理器.activateWindow(id) } else { 管理器.toggleMinimized(id) }
  }
}
</script>
