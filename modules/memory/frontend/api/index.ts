import { apiGet, apiPost } from '../../runtime'
import type { MemoryDeleteResult, MemoryListResult, MemoryRecord } from '../types'

export function listMemories(limit = 20, offset = 0): Promise<MemoryListResult> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return apiGet<MemoryListResult>(`/memory/list?${params.toString()}`)
}

export function recallMemories(query: string, limit = 10): Promise<MemoryRecord[]> {
  return apiPost<MemoryRecord[]>('/memory/recall', { query, limit, expand_chain: true })
}

export function deleteMemory(id: number): Promise<MemoryDeleteResult> {
  return apiPost<MemoryDeleteResult>('/memory/delete', { id })
}
