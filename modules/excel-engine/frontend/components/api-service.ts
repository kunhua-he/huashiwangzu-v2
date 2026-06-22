/**
 * Excel Engine - API Service Layer
 *
 * Handles all backend communication for the Excel editor.
 */
import { getApiUrl } from '../../runtime'

const TOKEN_KEY = 'v2_auth_token'

let __redirecting = false

function _handle401(status: number): boolean {
  if (status !== 401) return false
  localStorage.removeItem(TOKEN_KEY)
  if (!__redirecting) {
    __redirecting = true
    window.location.replace('/')
  }
  return true
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface CellEditRequest {
  state_key: string
  sheet: string
  address: string
  address_list?: string[]
  method: string
  value?: string
  params?: Record<string, unknown>
}

export interface StyleRequest {
  state_key: string
  sheet: string
  address_list: string[]
  method: string
  params?: Record<string, unknown>
}

export interface StateRequest {
  module: string
  method: string
  params?: Record<string, unknown>
  state_key: string
  sheet: string
}

export interface SheetData {
  cells: Record<string, string>
  styles: Record<string, Record<string, unknown>>
  merges: Record<string, { topLeft: string; rows: number; cols: number }>
  col_widths: Record<string, number>
  row_heights: Record<string, number>
  total_rows: number
  total_cols: number
}

export interface OpenResult extends SheetData {
  state_key: string
  all_sheets: string[]
  sheet_set: Record<string, unknown>
}

export interface EditResult {
  state_key?: string
  cells?: Record<string, string>
  styles?: Record<string, Record<string, unknown>>
  merges?: Record<string, { topLeft: string; rows: number; cols: number }>
  history?: HistoryItem[]
  total_rows?: number
  total_cols?: number
}

export interface HistoryItem {
  id: number
  action: string
  description?: string
  cell_addr?: string
  created_at: string
}

export interface ClipboardRequest {
  state_key: string
  sheet: string
  address: string
  address_list: string[]
  method: string
  params: Record<string, unknown>
}

function apiUrl(path: string): string {
  return getApiUrl(path)
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (_handle401(res.status)) throw new Error('登录已失效，请重新登录')
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`)
  const json = await res.json()
  if (!json.success) throw new Error(json.error || 'API error')
  return json.data as T
}

export async function openFile(fileId: number): Promise<OpenResult> {
  return post<OpenResult>('/excel-engine/open', { file_id: fileId })
}

export async function parseFile(fileId: number): Promise<EditResult> {
  return post<EditResult>('/excel-engine/parse', { file_id: fileId })
}

export async function editCell(req: CellEditRequest): Promise<EditResult> {
  return post<EditResult>('/excel-engine/edit', req)
}

export async function editStyle(req: StyleRequest): Promise<EditResult> {
  return post<EditResult>('/excel-engine/style', req)
}

export async function clipboardOp(req: ClipboardRequest): Promise<EditResult> {
  return post<EditResult>('/excel-engine/clipboard', req)
}

export async function tableOp(req: {
  state_key: string
  sheet: string
  address: string
  address_list: string[]
  method: string
  params: Record<string, unknown>
}): Promise<EditResult> {
  return post<EditResult>('/excel-engine/table', req)
}

export async function stateOp(req: StateRequest): Promise<EditResult> {
  return post<EditResult>('/excel-engine/state', req)
}

export async function dispatch(req: {
  module: string
  method: string
  params: Record<string, unknown>
  state_key: string
  sheet: string
}): Promise<EditResult> {
  return post<EditResult>('/excel-engine/dispatch', req)
}

export function getDownloadUrl(stateKey: string): string {
  return apiUrl(`/excel-engine/download/${stateKey}`)
}
