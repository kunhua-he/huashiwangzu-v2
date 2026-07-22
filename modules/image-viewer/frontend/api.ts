import { getApiUrl, authHeaders, handleUnauthorized } from '../runtime'

async function fetchBlob(fileId: number, variant: 'standard-image' | 'original'): Promise<Blob> {
  const url = getApiUrl(`/files/download/${fileId}/${variant}`)
  const resp = await fetch(url, { headers: authHeaders() })
  if (handleUnauthorized(resp.status)) throw new Error('登录已失效，请重新登录')
  if (!resp.ok) throw new Error(`Download returned ${resp.status}`)
  return resp.blob()
}

export async function downloadBlob(fileId: number): Promise<Blob> {
  try {
    return await fetchBlob(fileId, 'standard-image')
  } catch (error) {
    if (error instanceof Error && error.message === '登录已失效，请重新登录') throw error
    return await fetchBlob(fileId, 'original')
  }
}
