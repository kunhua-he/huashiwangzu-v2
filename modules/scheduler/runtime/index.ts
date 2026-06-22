interface ApiResponse<T = unknown> { success: boolean; data: T; error?: string }

const BASE = '/api/scheduler'

function apiBase(): string {
  const base = (typeof window !== 'undefined' && (window as any).__HSWZ_CONFIG__?.api_base_url) || ''
  return `${base}${BASE}`
}

function authHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('v2_auth_token') : null
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

export const scheduler = {
  async create(params: { title: string; scheduled_at?: string; recur?: string; action_description: string }): Promise<{ id: number; status: string }> {
    return apiPost('/create', params)
  },
  async list(): Promise<Array<{
    id: number; title: string; action_description: string; status: string;
    scheduled_at: string | null; recur: string | null; next_run_at: string | null;
    result: string | null; error_message: string | null; created_at: string | null;
  }>> {
    return apiGet('/list')
  },
  async cancel(taskId: number): Promise<{ id: number; status: string }> {
    return apiPost('/cancel', { task_id: taskId })
  },
}

export type SchedulerAPI = typeof scheduler
