import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'
import { collectDraggedFiles, uploadDraggedFiles } from '@/shared/upload/directory-upload'

export function useDesktopShellDropUpload() {
  const { emit } = useDesktopEventBus()
  const isDragActive = ref(false)

  function isExternalFile(e: DragEvent) {
    return Array.from(e.dataTransfer?.types || []).includes('Files')
  }

  function onDragEnter(e: DragEvent) {
    if (!isExternalFile(e)) return
    e.preventDefault()
    isDragActive.value = true
  }

  function onDragLeave(e: DragEvent) {
    if (!isExternalFile(e)) return
    e.preventDefault()
    isDragActive.value = false
  }

  async function onDrop(e: DragEvent) {
    if (!isExternalFile(e)) return
    e.preventDefault()
    isDragActive.value = false
    const fileList = await collectDraggedFiles(e.dataTransfer?.items || null)
    if (!fileList.length) return
    const result = await uploadDraggedFiles(fileList, null)
    emit('refresh:file-list', { folderId: 0 })
    if (result.successCount > 0) ElMessage.success(`Uploaded ${result.successCount} items to desktop`)
    if (result.failCount > 0) ElMessage.warning(`${result.failCount} items failed to upload`)
  }

  return { isDragActive, onDragEnter, onDragLeave, onDrop }
}
