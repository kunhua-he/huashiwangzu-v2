import { computed, onBeforeUnmount, ref, type Ref } from 'vue'
import {
  COLUMN_LIMITS,
  DEFAULT_COLUMN_WIDTHS,
  type ListColumnWidths,
  type ResizableColumn,
} from './fm-file-list-types'

export function useFmListColumnResize(options: {
  columnWidths: Ref<ListColumnWidths | undefined>
  onUpdate: (value: Required<ListColumnWidths>) => void
}) {
  const resizing = ref<null | { column: ResizableColumn; startX: number; startWidth: number }>(null)

  const resolvedColumnWidths = computed(() => ({
    name: options.columnWidths.value?.name ?? DEFAULT_COLUMN_WIDTHS.name,
    date: options.columnWidths.value?.date ?? DEFAULT_COLUMN_WIDTHS.date,
    type: options.columnWidths.value?.type ?? DEFAULT_COLUMN_WIDTHS.type,
    size: options.columnWidths.value?.size ?? DEFAULT_COLUMN_WIDTHS.size,
  }))

  const listGridStyle = computed(() => {
    const w = resolvedColumnWidths.value
    return {
      gridTemplateColumns: `24px minmax(${w.name}px, 1fr) 6px ${w.date}px 6px ${w.type}px 6px ${w.size}px 6px`,
    }
  })

  function clampColumnWidth(column: ResizableColumn, value: number) {
    const limit = COLUMN_LIMITS[column]
    return Math.min(limit.max, Math.max(limit.min, Math.round(value)))
  }

  function onColumnResizeMove(e: MouseEvent) {
    if (!resizing.value) return
    const delta = e.clientX - resizing.value.startX
    const nextWidth = clampColumnWidth(resizing.value.column, resizing.value.startWidth + delta)
    options.onUpdate({
      ...resolvedColumnWidths.value,
      [resizing.value.column]: nextWidth,
    })
  }

  function onColumnResizeEnd() {
    document.removeEventListener('mousemove', onColumnResizeMove)
    document.removeEventListener('mouseup', onColumnResizeEnd)
    resizing.value = null
  }

  function startColumnResize(column: ResizableColumn, e: MouseEvent) {
    resizing.value = {
      column,
      startX: e.clientX,
      startWidth: resolvedColumnWidths.value[column],
    }
    document.addEventListener('mousemove', onColumnResizeMove)
    document.addEventListener('mouseup', onColumnResizeEnd)
  }

  onBeforeUnmount(() => {
    onColumnResizeEnd()
  })

  return {
    listGridStyle,
    startColumnResize,
    onColumnResizeEnd,
  }
}
