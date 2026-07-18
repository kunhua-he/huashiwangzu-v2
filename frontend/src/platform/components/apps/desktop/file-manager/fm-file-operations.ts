import { useFileOperations } from '@/shared/files/use-file-operations'
import { useCreatableFormats } from '@/shared/composables/use-creatable-formats'
import { copyItems, cutItems, hasContent, currentClipboardType, currentClipboardItems, clearClipboard } from '@/desktop/clipboard/clipboard-state'
import { compressEntriesRequest, decompressZipRequest } from '@/shared/api/desktop'
import { pushUndo } from './finder-undo-stack'
import type { FileEntry } from '@/shared/api/types'
import type { ComputedRef, Ref } from 'vue'
import { ElMessage } from 'element-plus'

interface FileOperationsDeps {
  uploadInput: Ref<HTMLInputElement | null>
  currentFolderId: Ref<number>
  selectedItems: ComputedRef<FileEntry[]> | Ref<FileEntry[]>
  loadFiles: () => Promise<void>
  displayName: (file: FileEntry) => string
  openItem: (item: FileEntry) => void
  showProperties: (item: FileEntry) => void
  clearSelection?: () => void
  emit: {
    (event: 'refresh:file-list', payload: { folderId: number }): void
  }
}

function toClipboardItem(file: FileEntry, sourceFolderId?: number | null) {
  return {
    id: file.id,
    type: (file.is_folder ? 'folder' : 'file') as 'folder' | 'file',
    name: file.file_name,
    sourceFolderId: sourceFolderId ?? null,
  }
}

function resolveActionTargets(file: FileEntry | null, selected: FileEntry[]): FileEntry[] {
  if (file && selected.some((item) => item.id === file.id) && selected.length > 1) {
    return selected
  }
  if (file) return [file]
  return selected
}

export function createFileOperations(deps: FileOperationsDeps) {
  const { creatableFormats } = useCreatableFormats()
  /** target for "upload/create here" — null means current folder */
  let pendingTargetFolderId: number | null | undefined

  const ops = useFileOperations({
    refresh: async () => {
      await deps.loadFiles()
      deps.emit('refresh:file-list', { folderId: deps.currentFolderId.value })
    },
  })

  function resolveTargetFolderId(override?: number | null) {
    if (override !== undefined) return override
    if (pendingTargetFolderId !== undefined) return pendingTargetFolderId
    return deps.currentFolderId.value || null
  }

  function triggerUpload(targetFolderId?: number | null) {
    pendingTargetFolderId = targetFolderId
    deps.uploadInput.value?.click()
  }

  async function onUploadFile(e: Event) {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    input.value = ''
    const folderId = resolveTargetFolderId()
    pendingTargetFolderId = undefined
    await ops.uploadFile(file, folderId)
  }

  async function createFolder(parentId?: number | null) {
    const folderId = resolveTargetFolderId(parentId)
    pendingTargetFolderId = undefined
    await ops.createFolder(folderId)
  }

  async function createFileFromMenuKey(key: string, parentId?: number | null) {
    const ext = key.slice('create-file:'.length)
    const fmt = creatableFormats.value.find(format => format.extension === ext)
    const label = fmt?.label || `.${ext}`
    const folderId = resolveTargetFolderId(parentId)
    pendingTargetFolderId = undefined
    await ops.createFile(ext, folderId, label)
  }

  async function downloadFile(file: FileEntry) {
    await ops.downloadFile(file)
  }

  async function copyPath(file: FileEntry) {
    await ops.copyPath(file)
  }

  async function renameEntry(file: FileEntry) {
    const result = await ops.renameEntry(file)
    if (result?.renamed) {
      pushUndo({
        kind: 'rename',
        itemType: result.renamed.type,
        id: result.renamed.id,
        prevName: result.renamed.prevName,
        nextName: result.renamed.nextName,
      })
    }
    return result
  }

  async function deleteEntry(file: FileEntry) {
    await ops.deleteEntry(file)
  }

  async function deleteEntries(files: FileEntry[]) {
    const snapshot = files.map((f) => ({
      id: f.id,
      type: (f.is_folder ? 'folder' : 'file') as 'folder' | 'file',
    }))
    const result = await ops.deleteEntries(files)
    if (result && result.successCount > 0) {
      pushUndo({ kind: 'delete', items: snapshot })
      deps.clearSelection?.()
    }
    return result
  }

  async function moveEntries(files: FileEntry[], targetFolderId: number | null) {
    const from = deps.currentFolderId.value || null
    const snapshot = files.map((f) => ({
      id: f.id,
      type: (f.is_folder ? 'folder' : 'file') as 'folder' | 'file',
      from,
      to: targetFolderId,
    }))
    const result = await ops.moveEntries(files, targetFolderId)
    if (result.successCount > 0) {
      pushUndo({ kind: 'move', items: snapshot })
      deps.clearSelection?.()
    }
    return result
  }

  async function compressEntries(files: FileEntry[]) {
    if (!files.length) return
    try {
      const { blob, filename } = await compressEntriesRequest(
        files.map((f) => ({ id: f.id, item_type: f.is_folder ? 'folder' : 'file' })),
      )
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || '归档.zip'
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
      ElMessage.success(files.length > 1 ? `已压缩 ${files.length} 项` : '已压缩')
    } catch {
      ElMessage.warning('压缩失败')
    }
  }

  async function handleAction(key: string, file: FileEntry | null) {
    const selected = deps.selectedItems.value || []
    const targets = resolveActionTargets(file, selected)

    if (key === 'refresh') { await deps.loadFiles(); return }
    if (key === 'upload-file') {
      triggerUpload(deps.currentFolderId.value || null)
      return
    }
    if (key === 'upload-here') {
      // must land in the folder that was right-clicked
      const target = (file && file.is_folder) ? file.id : (deps.currentFolderId.value || null)
      triggerUpload(target)
      return
    }
    if (key === 'create-folder') {
      await createFolder(deps.currentFolderId.value || null)
      return
    }
    if (key === 'create-folder-here') {
      const target = (file && file.is_folder) ? file.id : (deps.currentFolderId.value || null)
      await createFolder(target)
      return
    }
    if (key.startsWith('create-file:')) {
      const target = (file && file.is_folder) ? file.id : (deps.currentFolderId.value || null)
      await createFileFromMenuKey(key, target)
      return
    }
    if (key === 'paste' || key === 'paste-here') {
      if (hasContent.value) {
        const isCut = currentClipboardType.value === 'cut'
        const folderId = (file && file.is_folder) ? file.id : deps.currentFolderId.value
        const clip = currentClipboardItems.value
        const result = await ops.pasteToFolder(folderId, clip, isCut)
        if (isCut) {
          pushUndo({
            kind: 'move',
            items: clip.map((c) => ({
              id: c.id,
              type: c.type,
              // undo back to where the item was cut from
              from: c.sourceFolderId ?? null,
              to: folderId,
            })),
          })
          clearClipboard()
        } else if (result.created?.length) {
          pushUndo({ kind: 'copy', created: result.created })
        }
      }
      return
    }
    if (key === 'properties' || key === 'details') {
      if (file) deps.showProperties(file)
      return
    }
    if (key === 'delete') {
      if (!targets.length) return
      await deleteEntries(targets)
      return
    }
    if (key === 'cut') {
      if (!targets.length) return
      const src = deps.currentFolderId.value || null
      cutItems(targets.map((t) => toClipboardItem(t, src)))
      ElMessage.success(targets.length > 1 ? `已剪切 ${targets.length} 项` : '已剪切')
      return
    }
    if (key === 'copy') {
      if (!targets.length) return
      const src = deps.currentFolderId.value || null
      copyItems(targets.map((t) => toClipboardItem(t, src)))
      ElMessage.success(targets.length > 1 ? `已复制 ${targets.length} 项` : '已复制')
      return
    }
    if (key === 'duplicate') {
      if (!targets.length) return
      const result = await ops.pasteToFolder(
        deps.currentFolderId.value || null,
        targets.map(toClipboardItem),
        false,
      )
      if (result.created?.length) pushUndo({ kind: 'copy', created: result.created })
      return
    }
    if (key === 'compress') {
      if (!targets.length) return
      await compressEntries(targets)
      return
    }
    if (key === 'decompress') {
      const target = file || targets[0]
      if (!target || target.is_folder) return
      const ext = String(target.format || '').toLowerCase()
      if (ext !== 'zip') {
        ElMessage.warning('仅支持 .zip 解压')
        return
      }
      try {
        const res = await decompressZipRequest(target.id, deps.currentFolderId.value || null)
        ElMessage.success(`已解压到「${res.folder_name}」(${res.file_count} 个文件)`)
        await deps.loadFiles()
      } catch {
        ElMessage.warning('解压失败')
      }
      return
    }
    if (!file) return
    if (key === 'open') { deps.openItem(file); return }
    if (key === 'download') { await downloadFile(file); return }
    if (key === 'copy-path') { await copyPath(file); return }
    if (key === 'rename') {
      await renameEntry(file)
      return
    }
  }

  return {
    triggerUpload,
    onUploadFile,
    createFolder,
    createFileFromMenuKey,
    downloadFile,
    copyPath,
    renameEntry,
    deleteEntry,
    deleteEntries,
    moveEntries,
    handleAction,
  }
}
