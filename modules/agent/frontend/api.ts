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

function getEventStreamUrl(path: string): string {
  const streamBase = getConfiguredStreamBaseUrl()
  return streamBase ? joinApiUrl(streamBase, path) : getApiUrl(path)
}

function getConfiguredStreamBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const runtimeBase = window.__HUASHI_RUNTIME__?.api_base_url || window.__HSWZ_CONFIG__?.api_base_url || ''
    if (runtimeBase && runtimeBase !== '/api') return runtimeBase
  }
  const env = import.meta.env as Record<string, string | undefined>
  return env.VITE_AGENT_STREAM_API_BASE_URL || env.VITE_API_BASE || env.VITE_API_TARGET || ''
}

function joinApiUrl(base: string, path: string): string {
  const normalizedBase = base.replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const baseHasApiPrefix = normalizedBase.endsWith('/api')
  const pathHasApiPrefix = normalizedPath.startsWith('/api/')
  if (baseHasApiPrefix && pathHasApiPrefix) {
    return `${normalizedBase}${normalizedPath.slice(4)}`
  }
  if (baseHasApiPrefix || pathHasApiPrefix) {
    return `${normalizedBase}${normalizedPath}`
  }
  return `${normalizedBase}/api${normalizedPath}`
}

export async function apiFetchEventStream(path: string, init?: RequestInit): Promise<Response> {
  const url = getEventStreamUrl(path)
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
