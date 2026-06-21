interface ApiResponse<T = unknown> { success: boolean; data: T; error?: string }

const BASE = '/api/memory'

function apiBase(): string {
  const base = (typeof window !== 'undefined' && (window as any).__HSWZ_CONFIG__?.api_base_url) || ''
  return `${base}${BASE}`
}

function authHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  const r = await fetch(`${apiBase()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: payload ? JSON.stringify(payload) : undefined,
  })
  const body: ApiResponse<T> = await r.json()
  if (!body.success) throw new Error(body.error ?? 'API error')
  return body.data as T
}

async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${apiBase()}${path}`, { headers: authHeaders() })
  const body: ApiResponse<T> = await r.json()
  if (!body.success) throw new Error(body.error ?? 'API error')
  return body.data as T
}

export interface MemoryItem {
  id: number
  text: string
  tags: string | null
  created_at: string | null
}

export const memory = {
  async save(params: { text: string; tags?: string }): Promise<{ id: number; status: string }> {
    return apiPost('/save', params)
  },
  async recall(params: { query: string; limit?: number }): Promise<MemoryItem[]> {
    return apiPost('/recall', params)
  },
  async list(): Promise<MemoryItem[]> {
    return apiGet('/list')
  },
  async delete(id: number): Promise<{ id: number; status: string }> {
    return apiPost('/delete', { id })
  },
}

export type MemoryAPI = typeof memory
