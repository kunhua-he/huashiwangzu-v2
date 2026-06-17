import type { MenuItemConfig } from './use-context-menu'

export function buildKnowledgeFolderMenu(writable: boolean, separatorItems: () => MenuItemConfig[]): MenuItemConfig[] {
  return [
    { key: 'refresh', label: '刷新', icon: '↻' },
    { key: 'upload-here', label: '上传到这里', icon: '⬆', disabled: !writable },
    { key: 'create-folder', label: '新建文件夹', icon: '+', disabled: !writable },
    ...separatorItems(),
    { key: 'analyze-folder', label: '分析此目录资料', icon: '⚙' },
    { key: 'view-progress', label: '查看分析进度', icon: '◷' },
    ...separatorItems(),
    { key: 'rename', label: '重命名', icon: '✎', disabled: !writable },
    { key: 'delete', label: '删除', icon: '🗑', disabled: !writable, danger: true },
  ]
}

export function buildKnowledgeFileMenu(writable: boolean, separatorItems: () => MenuItemConfig[]): MenuItemConfig[] {
  return [
    { key: 'open-reader', label: '打开阅读', icon: '📖' },
    { key: 'open-source-file', label: '打开源文件', icon: '↗' },
    { key: 'locate-folder', label: '在文件夹中定位', icon: '⌖' },
    ...separatorItems(),
    { key: 'start-analysis', label: '开始分析', icon: '⚙' },
    { key: 'rerun-analysis', label: '重新分析', icon: '⟳' },
    { key: 'view-progress', label: '查看分析进度', icon: '◷' },
    { key: 'view-evidence', label: '查看证据', icon: '✓' },
    ...separatorItems(),
    { key: 'rename', label: '重命名', icon: '✎', disabled: !writable },
    { key: 'delete', label: '删除', icon: '🗑', disabled: !writable, danger: true },
  ]
}
