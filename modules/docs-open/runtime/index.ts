const TOKEN_KEY = 'v2_auth_token'

let __redirecting = false

function _handle401(status: number): boolean {
  if (status !== 401) return false
  localStorage.removeItem(TOKEN_KEY)
  if (!__redirecting) {
    __redirecting = true
    window.location.replace('/')
  }
  return true
}

export function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const platform = {
  modules: {
    async call(targetModule: string, action: string, parameters: Record<string, unknown> = {}): Promise<unknown> {
      const r = await fetch('/api/modules/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ target_module: targetModule, action, parameters }),
      })
      if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
      const body = await r.json()
      if (!body.success) throw new Error(body.error ?? 'API error')
      return body.data
    },
  },
  docs: {
    async open(fileId: number, mode: string = 'view'): Promise<unknown> {
      const r = await fetch('/api/docs/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ file_id: fileId, mode }),
      })
      if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
      const body = await r.json()
      if (!body.success) throw new Error(body.error ?? 'Failed to open document')
      return body.data
    },
    async getContent(fileId: number): Promise<unknown> {
      const r = await fetch(`/api/docs/${fileId}/content`, { headers: authHeaders() })
      if (_handle401(r.status)) throw new Error('登录已失效，请重新登录')
      const body = await r.json()
      if (!body.success) throw new Error(body.error ?? 'Failed to get content')
      return body.data
    },
  },
}
