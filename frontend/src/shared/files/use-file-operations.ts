import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/shared/api'
import {
  createFileRequest, uploadFileRequest, renameEntryRequest,
  moveToRecycleBinRequest, moveEntryRequest, copyEntryRequest,
} from '@/shared/api/desktop'
import { formatFileDisplayName } from '@/shared/files/display-name'
import type { FileEntry } from '@/shared/api/types'

export type FileItemType = 'file' | 'folder'

export interface ClipboardLike {
  id: number
  type: FileItemType
  name: string
}

/** 统一文件全名：文件夹用原名，文件用显示名（含扩展名） */
export function fullFileName(file: FileEntry): string {
  return file.is_folder
    ? String(file.file_name || '')
    : formatFileDisplayName(file.file_name, file.format)
}

export interface FileOperationsOptions {
  /** 操作成功后的刷新回调，由调用方注入自己的刷新逻辑 */
  refresh: () => void | Promise<void>
}

export function useFileOperations(options: FileOperationsOptions) {
  const refresh = async () => { await options.refresh() }

  async function uploadFile(file: File, folderId: number | null): Promise<boolean> {
    try {
      await uploadFileRequest(file, folderId ?? undefined)
      ElMessage.success('上传成功')
      await refresh()
      return true
    } catch {
      ElMessage.warning('上传失败')
      return false
    }
  }

  async function createFolder(parentId: number | null): Promise<void> {
    try {
      const { value } = await ElMessageBox.prompt('文件夹名称', '新建文件夹', {
        confirmButtonText: '确定', cancelButtonText: '取消',
      })
      if (!value) return
      await api.post('/files/folder', { name: value, parent_id: parentId })
      ElMessage.success('已创建')
      await refresh()
    } catch { /* cancelled */ }
  }

  async function createFile(ext: string, folderId: number | null, label: string): Promise<void> {
    try {
      await createFileRequest(label, ext, folderId)
      ElMessage.success(`已创建 ${label}`)
      await refresh()
    } catch {
      ElMessage.warning('创建失败')
    }
  }

  async function downloadFile(file: FileEntry): Promise<void> {
    try {
      const res = await api.get(`/files/download/${file.id}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = fullFileName(file)
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      ElMessage.warning('下载失败')
    }
  }

  async function copyPath(file: FileEntry): Promise<void> {
    try {
      await navigator.clipboard.writeText(fullFileName(file))
      ElMessage.success('已复制路径')
    } catch {
      ElMessage.warning('复制失败')
    }
  }

  async function renameEntry(file: FileEntry): Promise<void> {
    try {
      const { value } = await ElMessageBox.prompt('输入新名称', '重命名', {
        inputValue: file.file_name, confirmButtonText: '确定', cancelButtonText: '取消',
      })
      if (!value || value === file.file_name) return
      await renameEntryRequest(file.is_folder ? 'folder' : 'file', file.id, value)
      ElMessage.success('重命名成功')
      await refresh()
    } catch { /* cancelled */ }
  }

  async function deleteEntry(file: FileEntry): Promise<void> {
    try {
      await ElMessageBox.confirm(`确定删除 "${file.file_name}"？`, '确认删除', { type: 'warning' })
    } catch {
      return
    }
    try {
      await moveToRecycleBinRequest(file.is_folder ? 'folder' : 'file', file.id)
      ElMessage.success('已移至回收站')
      await refresh()
    } catch {
      ElMessage.warning('删除失败')
    }
  }

  async function pasteToFolder(folderId: number | null, items: ClipboardLike[], isCut: boolean): Promise<void> {
    for (const item of items) {
      try {
        if (isCut) await moveEntryRequest(item.type, item.id, folderId)
        else await copyEntryRequest(item.type, item.id, folderId)
      } catch { /* skip failed item */ }
    }
    ElMessage.success(isCut ? '已移动' : '已粘贴')
    await refresh()
  }

  return {
    uploadFile, createFolder, createFile, downloadFile,
    copyPath, renameEntry, deleteEntry, pasteToFolder, fullFileName,
  }
}
