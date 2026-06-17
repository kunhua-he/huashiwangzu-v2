import type { MenuItemConfig } from './use-context-menu'

const openItem = (label: string, icon: string): MenuItemConfig => ({ key: 'open-app', label, icon })
const propertyItem: MenuItemConfig = { key: 'properties', label: '查看信息', icon: 'ⓘ' }

const iconMenuConfig: Record<string, (writable?: boolean, separatorItems?: () => MenuItemConfig[], buildRecycleMenu?: (writable?: boolean) => MenuItemConfig[]) => MenuItemConfig[]> = {
  recycle: (writable, _separatorItems, buildRecycleMenu) => buildRecycleMenu!(writable),
  desktop: (writable, separatorItems) => [
    openItem('打开', '📂'),
    ...separatorItems!(),
    { key: 'upload-file', label: '添加文件', icon: '⬆', disabled: !writable },
    { key: 'create-folder', label: '添加文件夹', icon: '📁', disabled: !writable },
  ],
  knowledge: (_writable, separatorItems) => [openItem('打开', '📚'), ...separatorItems!(), propertyItem],
  agent: (_writable, separatorItems) => [openItem('打开', '🤖'), ...separatorItems!(), propertyItem],
  settings: (_writable, separatorItems) => [openItem('打开', '⚙️'), ...separatorItems!(), propertyItem],
  tasks: (_writable, separatorItems) => [openItem('打开', '✅'), ...separatorItems!(), propertyItem],
}

export function buildDesktopShellBlankMenu(separatorItems: () => MenuItemConfig[]): MenuItemConfig[] {
  return [
    { key: 'view', label: '查看', icon: '⊞', children: [{ key: 'view-medium-icons', label: '中等图标', icon: '▦' }, { key: 'view-auto-arrange', label: '自动排列图标', icon: '⋮' }, { key: 'view-align-grid', label: '对齐网格', icon: '⌗' }] },
    { key: 'sort-by', label: '排序方式', icon: '⇅', children: [{ key: 'sort-name', label: '名称' }, { key: 'sort-type', label: '项目类型' }, { key: 'sort-date', label: '修改日期' }] },
    { key: 'new', label: '添加到桌面', icon: '+', children: [{ key: 'upload-file', label: '添加文件', icon: '⬆' }, { key: 'create-folder', label: '添加文件夹', icon: '📁' }] },
    { key: 'refresh-desktop', label: '刷新桌面', icon: '↻' },
    ...separatorItems(),
    { key: 'open-file-manager', label: 'openFile管理', icon: '📂' },
    { key: 'open-recycle-bin', label: '打开回收站', icon: '🗑' },
    ...separatorItems(),
    { key: 'open-start-menu', label: '打开开始菜单', icon: '⊞' },
  ]
}

export function buildDesktopShellIconMenu(appKey: string, writable?: boolean, separatorItems?: () => MenuItemConfig[], buildRecycleMenu?: (writable?: boolean) => MenuItemConfig[]): MenuItemConfig[] {
  return iconMenuConfig[appKey]?.(writable, separatorItems, buildRecycleMenu) ?? []
}
