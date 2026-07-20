import type { FileEntry } from '@/shared/api/types'

export type ColumnStackItem = {
  folderId: number
  name: string
  items: FileEntry[]
  selectedId: number | null
}

export type ListColumnWidths = {
  name?: number
  date?: number
  type?: number
  size?: number
}

export type ResizableColumn = 'name' | 'date' | 'type' | 'size'
export type FmSortColumn = 'name' | 'date' | 'type' | 'size'
export type FmViewMode = 'grid' | 'list' | 'column' | 'gallery'

export const DEFAULT_COLUMN_WIDTHS: Required<ListColumnWidths> = {
  name: 220,
  date: 132,
  type: 88,
  size: 72,
}

export const COLUMN_LIMITS: Record<ResizableColumn, { min: number; max: number }> = {
  name: { min: 120, max: 560 },
  date: { min: 96, max: 240 },
  type: { min: 64, max: 180 },
  size: { min: 56, max: 140 },
}
