/**
 * Excel Engine - API Service Layer
 *
 * Handles all backend communication for the Excel editor.
 */
import { platform } from '../runtime'

export interface CellEditRequest {
  state_key: string
  sheet: string
  address: string
  address_list?: string[]
  method: string
  value?: string
  params?: Record<string, any>
}

export interface StyleRequest {
  state_key: string
  sheet: string
  address_list: string[]
  method: string
  params?: Record<string, any>
}

export interface StateRequest {
  module: string
  method: string
  params?: Record<string, any>
  state_key: string
  sheet: string
}

export interface OpenResult {
  state_key: string
  cells: Record<string, string>
  styles: Record<string, Record<string, any>>
  merges: Record<string, { topLeft: string; rows: number; cols: number }>
  col_widths: Record<string, number>
  row_heights: Record<string, number>
  total_rows: number
  total_cols: number
  all_sheets: string[]
  sheet_set: Record<string, any>
}

function apiUrl(path: string): string {
  return platform.getApiUrl(path)
}

async function post<T>(path: string, body: any): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  return res.json() as Promise<T>
}

export async function openFile(fileId: number): Promise<OpenResult | null> {
  const json = await post<any>('/excel-engine/open', { file_id: fileId })
  if (json.success && json.data) return json.data as OpenResult
  return null
}

export async function parseFile(fileId: number): Promise<any> {
  const json = await post<any>('/excel-engine/parse', { file_id: fileId })
  if (json.success && json.data) return json.data
  return null
}

export async function editCell(req: CellEditRequest): Promise<any> {
  const json = await post<any>('/excel-engine/edit', req)
  return json.success ? json.data : null
}

export async function editStyle(req: StyleRequest): Promise<any> {
  const json = await post<any>('/excel-engine/style', req)
  return json.success ? json.data : null
}

export async function clipboardOp(req: {
  state_key: string
  sheet: string
  address: string
  address_list: string[]
  method: string
  params: Record<string, any>
}): Promise<any> {
  const json = await post<any>('/excel-engine/clipboard', req)
  return json.success ? json.data : null
}

export async function tableOp(req: {
  state_key: string
  sheet: string
  address: string
  address_list: string[]
  method: string
  params: Record<string, any>
}): Promise<any> {
  const json = await post<any>('/excel-engine/table', req)
  return json.success ? json.data : null
}

export async function stateOp(req: StateRequest): Promise<any> {
  const json = await post<any>('/excel-engine/state', req)
  return json.success ? json.data : null
}

export async function dispatch(req: {
  module: string
  method: string
  params: Record<string, any>
  state_key: string
  sheet: string
}): Promise<any> {
  const json = await post<any>('/excel-engine/dispatch', req)
  return json.success ? json.data : null
}

export function getDownloadUrl(stateKey: string): string {
  return apiUrl(`/excel-engine/download/${stateKey}`)
}
