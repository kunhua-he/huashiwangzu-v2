const TOKEN_KEY = 'v2_auth_token'

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function getApiUrl(path: string): string {
  const base = '/api'
  return `${base}${path}`
}
