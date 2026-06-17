import { 获取文件夹树请求, 新建文件夹请求, 上传文件请求 } from '@/shared/api/desktop'

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
  const treeResponse = await 获取文件夹树请求()
  const index = new Map<string, number>()
  if (treeResponse.success && treeResponse.data) {
    for (const item of treeResponse.data) index.set(`${item.parent_folder_id ?? 0}/${item.name}`, item.id)
  }

  async function ensureDirectory(path: string[]) {
    let parentId = rootFolderId ?? 0
    for (const name of path) {
      const key = `${parentId}/${name}`
      if (!index.has(key)) {
        const res = await 新建文件夹请求(name, parentId || null)
        index.set(key, ((res.data as unknown as Record<string, unknown>)?.id as number) ?? 0)
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
      const res = await 上传文件请求(item.file, folderId)
      if (res.success) successCount++
      else failCount++
    } catch {
      failCount++
    }
  }
  return { successCount, failCount }
}
