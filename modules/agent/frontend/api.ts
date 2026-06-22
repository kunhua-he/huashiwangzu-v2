import { getApiUrl, authHeaders, _handle401 } from '../runtime'

export interface ApiBody<T> { success: boolean; data: T; error?: string | null }

export async function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path)
}

export async function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload ? JSON.stringify(payload) : undefined,
  })
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = getApiUrl(path)
  const { headers: initHeaders, ...restInit } = init || {}
  const r = await fetch(url, { headers: { ...(initHeaders as Record<string, string> || {}), ...authHeaders() }, ...restInit })
  if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
  const body: ApiBody<T> = await r.json()
  if (!body.success) throw new Error(body.error || '请求失败')
  return body.data as T
}

export async function apiFetchRaw(path: string, init?: RequestInit): Promise<Response> {
  const url = getApiUrl(path)
  const { headers: initHeaders, ...restInit } = init || {}
  const resp = await fetch(url, { headers: { ...(initHeaders as Record<string, string> || {}), ...authHeaders() }, ...restInit })
  if (_handle401(resp.status)) throw new Error('登录已失效，请重新登录')
  return resp
}

export async function apiPut<T>(path: string, payload?: unknown): Promise<T> {
  const url = getApiUrl(path)
  const r = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: payload ? JSON.stringify(payload) : undefined,
  })
  if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
  if (!r.ok) throw new Error(`API ${path} returned ${r.status}`)
  const body = await r.json()
  if (!body.success) throw new Error(body.error || '请求失败')
  return body.data as T
}

export async function apiDelete<T>(path: string): Promise<T> {
  const url = getApiUrl(path)
  const r = await fetch(url, { method: 'DELETE', headers: authHeaders() })
  if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
  if (!r.ok) throw new Error(`API ${path} returned ${r.status}`)
  const body = await r.json()
  if (!body.success) throw new Error(body.error || '请求失败')
  return body.data as T
}
