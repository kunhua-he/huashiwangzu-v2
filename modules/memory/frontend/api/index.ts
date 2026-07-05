import { apiGet, apiPost } from '../../runtime'
import type { MemoryRecord } from '../types'

export interface MemoryListResponse {
  items?: MemoryRecord[]
  total?: number
}

export type MemoryListResult = MemoryRecord[] | MemoryListResponse

export function listMemories(limit = 20, offset = 0): Promise<MemoryListResult> {
  return apiGet<MemoryListResult>(`/memory/list?limit=${limit}&offset=${offset}`)
}

export function recallMemories(query: string, limit = 5): Promise<MemoryRecord[]> {
  return apiPost<MemoryRecord[]>('/memory/recall', { query, limit })
}
