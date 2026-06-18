import { useFileOperations } from '@/shared/files/use-file-operations'
import { useCreatableFormats } from '@/shared/composables/use-creatable-formats'
import type { FileEntry } from '@/shared/api/types'
import type { Ref } from 'vue'

interface FileOperationsDeps {
  uploadInput: Ref<HTMLInputElement | null>
  currentFolderId: Ref<number>
  loadFiles: () => Promise<void>
  displayName: (file: FileEntry) => string
  ctxTarget: Ref<FileEntry | null>
  closeContextMenu: () => void
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

  async function handleCtxClick(key: string) {
    deps.closeContextMenu()
    const file = deps.ctxTarget.value
    if (key === 'refresh') { await deps.loadFiles(); return }
    if (key === 'upload-file') { triggerUpload(); return }
    if (key === 'create-folder') { await createFolder(); return }
    if (key.startsWith('create-file:')) {
      await createFileFromMenuKey(key)
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
    if (key === 'delete') { await deleteEntry(file) }
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
    handleCtxClick,
  }
}
