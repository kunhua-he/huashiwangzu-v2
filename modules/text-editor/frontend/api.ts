import { getApiUrl, authHeaders, handleUnauthorized } from '../runtime'

export interface ContentNode {
  id?: string
  kind?: string
  parent_id?: string | null
  order?: number
  text?: string
  attrs?: Record<string, unknown>
}

export interface HydratedContentPackage {
  profile?: string
  schema_version?: string
  total?: number
  nodes?: ContentNode[]
}

export async function hydrateTextPackage(packageId: number, versionId?: number | null): Promise<HydratedContentPackage> {
  const qs = new URLSearchParams()
  if (versionId) qs.set('version_id', String(versionId))
  qs.set('limit', '2000')
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  const resp = await fetch(getApiUrl(`/content/packages/${packageId}/hydrate${suffix}`), { headers: authHeaders() })
  if (handleUnauthorized(resp.status)) throw new Error('登录已失效，请重新登录')
  if (!resp.ok) throw new Error(`Hydrate returned ${resp.status}`)
  const body = await resp.json()
  if (!body.success) throw new Error(body.error ?? 'Hydrate error')
  return body.data as HydratedContentPackage
}

export async function saveTextPackage(
  packageId: number,
  payload: {
    expectedVersionId?: number | null
    content: Record<string, unknown>
    summary?: string
    autosave?: boolean
  },
): Promise<Record<string, unknown>> {
  const resp = await fetch(getApiUrl(`/content/packages/${packageId}/save`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (handleUnauthorized(resp.status)) throw new Error('登录已失效，请重新登录')
  if (!resp.ok) throw new Error(`Save returned ${resp.status}`)
  const body = await resp.json()
  if (!body.success) throw new Error(body.error ?? 'Save error')
  return body.data as Record<string, unknown>
}
