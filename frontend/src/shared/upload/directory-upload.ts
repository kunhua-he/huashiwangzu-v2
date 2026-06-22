import { createFolderRequest, fetchFolderTree, uploadFileRequest } from '@/shared/api/desktop'
import type { FolderEntry } from '@/shared/api/types'

interface FileToUpload { file: File; path: string[] }

function readDirectory(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise(resolve => reader.readEntries(resolve))
}

async function expandEntry(entry: FileSystemEntry, path: string[] = []): Promise<FileToUpload[]> {
  if (entry.isFile) {
    return new Promise(resolve => (entry as FileSystemFileEntry).file(f => resolve([{ file: f, path }])))
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader()
  const currentPath = [...path, entry.name]
  const results: FileToUpload[] = []
  while (true) {
    const batch = await readDirectory(reader)
    if (!batch.length) break
    for (const child of batch) results.push(...await expandEntry(child, currentPath))
  }
  return results
}

export async function collectDraggedFiles(items: DataTransferItemList | null): Promise<FileToUpload[]> {
  if (!items) return []
  const results: FileToUpload[] = []
  for (let i = 0; i < items.length; i++) {
    const entry = items[i].webkitGetAsEntry?.()
    if (entry) results.push(...await expandEntry(entry))
    else {
      const f = items[i].getAsFile?.()
      if (f) results.push({ file: f, path: [] })
    }
  }
  return results
}

export async function uploadDraggedFiles(fileList: FileToUpload[], rootFolderId?: number | null) {
  let treeData: FolderEntry[] = []
  try {
    treeData = await fetchFolderTree()
  } catch {
    treeData = []
  }
  const index = new Map<string, number>()
  for (const item of treeData) index.set(`${item.parent_folder_id ?? 0}/${item.name}`, item.id)

  async function ensureDirectory(path: string[]) {
    let parentId = rootFolderId ?? 0
    for (const name of path) {
      const key = `${parentId}/${name}`
      if (!index.has(key)) {
        try {
          const folder = await createFolderRequest(name, parentId || null)
          index.set(key, folder.id)
        } catch {
          // if folder already exists, skip
        }
      }
      parentId = index.get(key)!
    }
    return parentId || undefined
  }

  let successCount = 0
  let failCount = 0
  for (const item of fileList) {
    try {
      const folderId = await ensureDirectory(item.path)
      await uploadFileRequest(item.file, folderId)
      successCount++
    } catch {
      failCount++
    }
  }
  return { successCount, failCount }
}
