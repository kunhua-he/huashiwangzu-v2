import api, { API_BASE_URL } from './index'
import type { FolderEntry, FileEntry, RecycleBinEntry, FileDetail } from './types'
export type { FileOpenPayload as FilePreviewPayload } from '@/desktop/window-manager/window-types'
import type { DesktopPersistentState } from '@/desktop/window-manager/desktop-state-store'

type FileItemType = 'file' | 'folder'

interface BackendFileListItem {
  id: number
  name: string
  extension?: string | null
  size: number
  parent_id?: number | null
  created_at?: string | null
  is_folder: boolean
  mime_type?: string | null
  storage_path?: string | null
}

interface BackendFileListResponse {
  items: BackendFileListItem[]
  total: number
  page: number
  page_size: number
}

interface BackendDesktopStateResponse {
  user_id: number
  state_json: Partial<DesktopPersistentState> & {
    版本?: number
    窗口?: DesktopPersistentState['windows']
    应用状态?: DesktopPersistentState['appState']
    图标位置?: DesktopPersistentState['iconPositions']
  }
  version: number
}

interface UploadFileResponse {
  exists: boolean
  deduplicated?: boolean
  id: number
  name: string
  extension: string
  size?: number | null
  mime_type?: string | null
}

export interface FileListPageResponse {
  items: FileEntry[]
  total: number
  page: number
  page_size: number
}

function toFileEntry(item: BackendFileListItem): FileEntry {
  return {
    id: item.id,
    file_name: item.name,
    format: item.extension ?? null,
    file_size: item.size,
    created_at: item.created_at ?? '',
    storage_path: item.storage_path ?? null,
    is_folder: item.is_folder,
    parent_folder_id: item.parent_id ?? null,
  }
}

function toFileListPage(data: BackendFileListResponse): FileListPageResponse {
  return {
    items: data.items.map(toFileEntry),
    total: data.total,
    page: data.page,
    page_size: data.page_size,
  }
}

function toDesktopPersistentState(response: BackendDesktopStateResponse): DesktopPersistentState {
  const payload = response.state_json || {}
  return {
    version: payload.version ?? payload.版本 ?? response.version ?? 1,
    windows: Array.isArray(payload.windows) ? payload.windows : Array.isArray(payload.窗口) ? payload.窗口 : [],
    appState: payload.appState ?? payload.应用状态 ?? {},
    iconPositions: payload.iconPositions ?? payload.图标位置 ?? {},
  }
}

export async function readDesktopStateRequest(): Promise<DesktopPersistentState> {
  const data = await api.get<unknown, BackendDesktopStateResponse>('/desktop/state')
  return toDesktopPersistentState(data)
}

export async function saveDesktopStateRequest(state: DesktopPersistentState): Promise<DesktopPersistentState> {
  const data = await api.post<unknown, BackendDesktopStateResponse>('/desktop/state', { state_json: state })
  return toDesktopPersistentState(data)
}

export async function fetchFolderTree(): Promise<FolderEntry[]> {
  return await api.get<unknown, FolderEntry[]>('/files/tree')
}

export async function fetchFileList(folderId: number, page = 1, pageSize = 50): Promise<FileListPageResponse> {
  const data = await api.get<unknown, BackendFileListResponse>('/files/list', {
    params: { folder_id: folderId, page, page_size: pageSize },
  })
  return toFileListPage(data)
}

export async function createFolderRequest(name: string, parentFolderId?: number | null): Promise<FolderEntry> {
  return await api.post<unknown, FolderEntry>('/files/folder', { name, parent_id: parentFolderId })
}

export async function renameEntryRequest(itemType: FileItemType, id: number, newName: string): Promise<Record<string, unknown>> {
  return await api.post<unknown, Record<string, unknown>>('/files/rename', { type: itemType, id, new_name: newName })
}

export async function moveEntryRequest(itemType: FileItemType, id: number, targetFolderId?: number | null): Promise<Record<string, unknown>> {
  return await api.post<unknown, Record<string, unknown>>('/files/move', { type: itemType, id, target_folder_id: targetFolderId })
}

export async function copyEntryRequest(itemType: FileItemType, id: number, targetFolderId?: number | null): Promise<Record<string, unknown>> {
  return await api.post<unknown, Record<string, unknown>>('/files/copy', { type: itemType, id, target_folder_id: targetFolderId })
}

export async function moveToRecycleBinRequest(itemType: FileItemType, id: number): Promise<Record<string, unknown>> {
  return await api.post<unknown, Record<string, unknown>>('/files/delete', { type: itemType, id })
}

export function downloadFileRequest(fileId: number) {
  window.open(`${API_BASE_URL}/files/download/${fileId}`, '_blank')
}

interface CreateFileResponse {
  id: number
  name: string
  extension: string
  size: number
  mime_type: string
  deduplicated: boolean
}

export async function createFileRequest(name: string, extension: string, folderId?: number | null): Promise<CreateFileResponse> {
  return await api.post<unknown, CreateFileResponse>('/files/create-file', {
    name, extension, folder_id: folderId || null,
  })
}

export async function uploadFileRequest(file: File, folderId?: number, onProgress?: (pct: number) => void): Promise<UploadFileResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (folderId !== undefined) {
    formData.append('folder_id', String(folderId))
  }
  return await api.post<unknown, UploadFileResponse>('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress
      ? (e) => {
          if (e.total) {
            onProgress(Math.round((e.loaded / e.total) * 100))
          }
        }
      : undefined,
  })
}

export async function fetchRecycleBinList(): Promise<RecycleBinEntry[]> {
  return await api.get<unknown, RecycleBinEntry[]>('/recycle/list')
}

export async function restoreRecycleBinEntry(itemType: FileItemType, id: number): Promise<Record<string, unknown>> {
  return await api.post<unknown, Record<string, unknown>>('/recycle/restore', { item_type: itemType, id })
}

export async function permanentlyDeleteEntry(itemType: FileItemType, id: number): Promise<Record<string, unknown>> {
  return await api.post<unknown, Record<string, unknown>>('/recycle/delete-permanently', { item_type: itemType, id })
}

export async function emptyRecycleBinRequest(): Promise<{ message: string }> {
  return await api.post<unknown, { message: string }>('/recycle/empty')
}

export interface FileSearchPageResponse {
  items: FileEntry[]
  total: number
  page: number
  page_size: number
}

export async function searchFilesRequest(keyword: string, extension?: string, page = 1, pageSize = 50): Promise<FileSearchPageResponse> {
  const data = await api.get<unknown, BackendFileListResponse>('/files/search', {
    params: { keyword, extension, page, page_size: pageSize }
  })
  return toFileListPage(data)
}

export async function fetchFileDetail(fileId: number): Promise<FileDetail> {
  return await api.get<unknown, FileDetail>(`/files/detail/${fileId}`)
}

export async function fetchFilePreview(fileId: number): Promise<Record<string, unknown>> {
  return await api.get<unknown, Record<string, unknown>>(`/files/preview/${fileId}`)
}

export function getFilePreviewUrl(fileId: number): string {
  return `${API_BASE_URL}/files/preview/${fileId}`
}
