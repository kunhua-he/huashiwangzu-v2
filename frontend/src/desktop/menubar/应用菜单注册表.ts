/**
 * 前台 App 菜单注入注册表。
 * App 可注册额外菜单段；菜单栏按 activeAppKey 读取。
 */
export interface 菜单项 {
  id: string
  label: string
  icon?: string
  shortcut?: string
  disabled?: boolean
  danger?: boolean
  separator?: boolean
  command?: string
  /** 打开 app */
  openApp?: string
  payload?: Record<string, unknown>
}

export interface 菜单段 {
  key: string
  label: string
  items: 菜单项[]
}

type 菜单提供器 = (ctx: { appKey: string; windowId?: string; title: string }) => 菜单段[]

const 提供器表 = new Map<string, 菜单提供器>()

export function 注册应用菜单(appKey: string, 提供器: 菜单提供器): () => void {
  提供器表.set(appKey, 提供器)
  return () => {
    if (提供器表.get(appKey) === 提供器) 提供器表.delete(appKey)
  }
}

export function 读取应用菜单(appKey: string, ctx: { windowId?: string; title: string }): 菜单段[] {
  if (!appKey) return []
  const keys = new Set([appKey])
  if (appKey === 'desktop') keys.add('files')
  if (appKey === 'files') keys.add('desktop')
  for (const key of keys) {
    const fn = 提供器表.get(key)
    if (fn) return fn({ appKey: key, windowId: ctx.windowId, title: ctx.title })
  }
  return []
}

/** 内置访达菜单（始终可用，无需各处重复注册） */
export function 访达默认菜单(): 菜单段[] {
  return [
    {
      key: 'file',
      label: '文件',
      items: [
        { id: 'finder-new-window', label: '新建访达窗口', command: 'finder:new-window', shortcut: '⌃⇧H' },
        { id: 'finder-new-folder', label: '新建文件夹', command: 'new-folder' },
        { id: 'sep-f1', label: '', separator: true },
        { id: 'finder-close', label: '关闭窗口', command: 'close-active' },
      ],
    },
    {
      key: 'go',
      label: '前往',
      items: [
        { id: 'go-desktop', label: '桌面', openApp: 'desktop', payload: { folderId: 0, folderName: '桌面' } },
        { id: 'go-documents', label: '文稿', command: 'finder-go-documents' },
        { id: 'go-downloads', label: '下载', command: 'finder-go-downloads' },
        { id: 'sep-g1', label: '', separator: true },
        { id: 'go-recycle', label: '回收站', openApp: 'recycle' },
      ],
    },
    {
      key: 'view',
      label: '显示',
      items: [
        { id: 'view-icons', label: '图标', command: 'finder-view-icons' },
        { id: 'view-list', label: '列表', command: 'finder-view-list' },
        { id: 'view-columns', label: '分栏', command: 'finder-view-columns' },
        { id: 'view-gallery', label: '画廊', command: 'finder-view-gallery' },
      ],
    },
  ]
}

// 启动时注册访达
注册应用菜单('desktop', () => 访达默认菜单())
注册应用菜单('files', () => 访达默认菜单())
