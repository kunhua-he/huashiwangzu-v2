export interface DesktopFileManagerBreadcrumbItem {
  id: number | null
  name: string
}

export interface NavigationEntry {
  id: number
  name: string
}

export interface DesktopFileManagerMenuItem {
  key: string
  label: string
  icon?: string
  disabled?: boolean
  danger?: boolean
}
