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

export async function downloadBlob(fileId: number): Promise<Blob> {
  const url = getApiUrl(`/files/download/${fileId}`)
  const resp = await fetch(url, { headers: authHeaders() })
  if (_handle401(resp.status)) throw new Error('登录已失效，请重新登录')
  if (!resp.ok) throw new Error(`Download returned ${resp.status}`)
  return resp.blob()
}
