const TOKEN_KEY = 'v2_auth_token'

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function getApiUrl(path: string): string {
  const base = '/api'
  return `${base}${path}`
}

export async function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  const r = await fetch(getApiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: payload ? JSON.stringify(payload) : undefined,
  })
  const j = await r.json()
  if (!j.success) throw new Error(j.error || 'API error')
  return j.data as T
}
