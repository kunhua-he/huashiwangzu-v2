import { ref } from 'vue'
import type { FileEntry } from '@/shared/api/types'

export function useFmInlineRename(options: {
  isSelected: (id: number) => boolean
  onRename: (item: FileEntry, nextName: string) => void
}) {
  const renamingId = ref<number | null>(null)
  const renameDraft = ref('')
  let renameClickTimer: ReturnType<typeof setTimeout> | null = null
  let lastRenameClickId: number | null = null

  function startInlineRename(item: FileEntry) {
    renamingId.value = item.id
    renameDraft.value = item.file_name
    requestAnimationFrame(() => {
      const el = document.querySelector('.fm-inline-rename') as HTMLInputElement | null
      el?.focus()
      el?.select()
    })
  }

  function cancelInlineRename() {
    renamingId.value = null
    renameDraft.value = ''
  }

  function commitInlineRename(item: FileEntry) {
    if (renamingId.value !== item.id) return
    const next = renameDraft.value.trim()
    renamingId.value = null
    renameDraft.value = ''
    if (!next || next === item.file_name) return
    options.onRename(item, next)
  }

  function maybeStartInlineRename(item: FileEntry, e: MouseEvent) {
    if (!options.isSelected(item.id)) return
    if (lastRenameClickId === item.id) {
      if (renameClickTimer) clearTimeout(renameClickTimer)
      renameClickTimer = null
      lastRenameClickId = null
      startInlineRename(item)
      e.preventDefault()
      return
    }
    lastRenameClickId = item.id
    if (renameClickTimer) clearTimeout(renameClickTimer)
    renameClickTimer = setTimeout(() => {
      lastRenameClickId = null
      renameClickTimer = null
    }, 900)
  }

  return {
    renamingId,
    renameDraft,
    maybeStartInlineRename,
    startInlineRename,
    cancelInlineRename,
    commitInlineRename,
  }
}
