import { useFileOperations } from '@/shared/files/use-file-operations'
import { useCreatableFormats } from '@/shared/composables/use-creatable-formats'
import { copyItems, cutItems, hasContent, currentClipboardType, currentClipboardItems, clearClipboard } from '@/desktop/clipboard/clipboard-state'
import type { FileEntry } from '@/shared/api/types'
import type { Ref } from 'vue'

interface FileOperationsDeps {
  uploadInput: Ref<HTMLInputElement | null>
  currentFolderId: Ref<number>
  loadFiles: () => Promise<void>
  displayName: (file: FileEntry) => string
  openItem: (item: FileEntry) => void
  showProperties: (item: FileEntry) => void
  emit: {
    (event: 'refresh:file-list', payload: { folderId: number }): void
  }
}

export function createFileOperations(deps: FileOperationsDeps) {
  const { creatableFormats } = useCreatableFormats()

  const ops = useFileOperations({
    refresh: async () => {
      await deps.loadFiles()
      deps.emit('refresh:file-list', { folderId: deps.currentFolderId.value })
    },
  })

  function triggerUpload() {
    deps.uploadInput.value?.click()
  }

  async function onUploadFile(e: Event) {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    input.value = ''
    await ops.uploadFile(file, deps.currentFolderId.value || null)
  }

  async function createFolder() {
    await ops.createFolder(deps.currentFolderId.value || null)
  }

  async function createFileFromMenuKey(key: string) {
    const ext = key.slice('create-file:'.length)
    const fmt = creatableFormats.value.find(format => format.extension === ext)
    const label = fmt?.label || `.${ext}`
    await ops.createFile(ext, deps.currentFolderId.value || null, label)
  }

  async function downloadFile(file: FileEntry) {
    await ops.downloadFile(file)
  }

  async function copyPath(file: FileEntry) {
    await ops.copyPath(file)
  }

  async function renameEntry(file: FileEntry) {
    await ops.renameEntry(file)
  }

  async function deleteEntry(file: FileEntry) {
    await ops.deleteEntry(file)
  }

  async function handleAction(key: string, file: FileEntry | null) {
    if (key === 'refresh') { await deps.loadFiles(); return }
    if (key === 'upload-file' || key === 'upload-here') { triggerUpload(); return }
    if (key === 'create-folder' || key === 'create-folder-here') { await createFolder(); return }
    if (key.startsWith('create-file:')) {
      await createFileFromMenuKey(key)
      return
    }
    if (key === 'paste' || key === 'paste-here') {
      if (hasContent.value) {
        const isCut = currentClipboardType.value === 'cut'
        const folderId = (file && file.is_folder) ? file.id : deps.currentFolderId.value
        await ops.pasteToFolder(folderId, currentClipboardItems.value, isCut)
        if (isCut) clearClipboard()
      }
      return
    }
    if (key === 'properties' || key === 'details') {
      if (file) deps.showProperties(file)
      return
    }
    if (!file) return
    if (key === 'open') { deps.openItem(file); return }
    if (key === 'download') { await downloadFile(file); return }
    if (key === 'copy-path') { await copyPath(file); return }
    if (key === 'rename') { await renameEntry(file); return }
    if (key === 'delete') { await deleteEntry(file); return }
    if (key === 'cut') { cutItems([{ id: file.id, type: file.is_folder ? 'folder' as const : 'file' as const, name: file.file_name }]); return }
    if (key === 'copy') { copyItems([{ id: file.id, type: file.is_folder ? 'folder' as const : 'file' as const, name: file.file_name }]); return }
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
    handleAction,
  }
}
