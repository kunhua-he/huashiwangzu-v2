import { getApiUrl, authHeaders } from '../runtime'

let __redirecting = false

function _handle401(status: number): boolean {
  if (status !== 401) return false
  localStorage.removeItem('v2_auth_token')
  if (!__redirecting) {
    __redirecting = true
    window.location.replace('/')
  }
  return true
}

export async function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  const url = getApiUrl(path)
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: payload ? JSON.stringify(payload) : undefined,
  })
  if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
  if (!r.ok) throw new Error(`API ${path} returned ${r.status}`)
  const body = await r.json()
  if (!body.success) throw new Error(body.error ?? 'API error')
  return body.data as T
}

export async function downloadText(fileId: number): Promise<string> {
  const url = getApiUrl(`/files/download/${fileId}`)
  const resp = await fetch(url, { headers: authHeaders() })
  if (_handle401(resp.status)) throw new Error('登录已失效，请重新登录')
  if (!resp.ok) throw new Error(`Download returned ${resp.status}`)
  return resp.text()
}
