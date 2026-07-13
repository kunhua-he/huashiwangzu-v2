import type { RefItem } from '../types'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function identifierValue(value: unknown): string | number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) return value.trim()
  return null
}

function normalizedType(value: Record<string, unknown>): string {
  const type = textValue(value.type) || textValue(value.resource_type)
  if (type === 'web') return 'url'
  if (type) return type
  if (identifierValue(value.file_id) !== null || identifierValue(value.source_file_id) !== null) return 'file'
  if (textValue(value.url) || textValue(value.open_url)) return 'url'
  if (identifierValue(value.document_id) !== null || identifierValue(value.chunk_id) !== null) return 'record'
  return ''
}

/** Convert persisted pre-ResourceRef messages at the input boundary only. */
export function normalizeRefItem(value: unknown): RefItem | null {
  if (!isRecord(value)) return null

  const type = normalizedType(value)
  if (!type) return null

  const canonicalLocator = textValue(value.locator)
  const legacyLocator = textValue(value.url) || textValue(value.open_url) || textValue(value.download_url)
  const locator = canonicalLocator || legacyLocator

  let id = identifierValue(value.id)
  if (id === null && type === 'file') {
    id = identifierValue(value.file_id) ?? identifierValue(value.source_file_id)
  } else if (id === null && type === 'url') {
    id = locator || null
  } else if (id === null) {
    id = identifierValue(value.chunk_id)
      ?? identifierValue(value.document_id)
      ?? identifierValue(value.file_id)
      ?? identifierValue(value.source_file_id)
      ?? (locator || null)
  }

  const displayName = textValue(value.display_name)
    || textValue(value.label)
    || textValue(value.title)
    || textValue(value.source)
    || locator
    || (id === null ? '' : `${type} ${String(id)}`)
  if (id === null && !displayName) return null

  const provenance = isRecord(value.provenance) ? { ...value.provenance } : {}
  if (value.excerpt !== undefined && provenance.excerpt === undefined) provenance.excerpt = value.excerpt
  if (value.page !== undefined && provenance.page === undefined) provenance.page = value.page
  if (value.section !== undefined && provenance.section === undefined) provenance.section = value.section
  if (value.format !== undefined && provenance.format === undefined) provenance.format = value.format

  return {
    type,
    id: id ?? `legacy:${type}:${displayName}`,
    display_name: displayName,
    locator,
    mime_type: textValue(value.mime_type),
    access_scope: textValue(value.access_scope) || 'user',
    provenance,
  }
}

export function normalizeRefItems(value: unknown): RefItem[] {
  if (!Array.isArray(value)) return []
  const refs: RefItem[] = []
  for (const item of value) {
    const ref = normalizeRefItem(item)
    if (ref) refs.push(ref)
  }
  return uniqueRefs(refs)
}

export function referenceKey(ref: RefItem): string {
  return `${ref.type}:${String(ref.id)}:${ref.locator}`
}

export function uniqueRefs(refs: readonly RefItem[]): RefItem[] {
  const seen = new Set<string>()
  const out: RefItem[] = []
  for (const ref of refs) {
    const key = referenceKey(ref)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(ref)
  }
  return out
}

export function referenceDisplayName(ref: RefItem): string {
  return ref.display_name.trim() || ref.locator.trim() || `${ref.type} ${String(ref.id)}`
}

export function referenceExcerpt(ref: RefItem): string {
  const excerpt = ref.provenance.excerpt ?? ref.provenance.snippet
  return typeof excerpt === 'string' ? excerpt.trim() : ''
}

export function referenceOpenTarget(ref: RefItem): string {
  if (ref.type === 'url') return ref.locator.trim()
  if (ref.type !== 'file') return ''

  const fileId = Number(ref.id)
  if (!Number.isInteger(fileId) || fileId <= 0) return ''
  const query = new URLSearchParams({
    file_id: String(fileId),
    file_name: referenceDisplayName(ref),
  })
  const format = ref.provenance.format
  const page = ref.provenance.page
  if (typeof format === 'string' && format.trim()) query.set('format', format.trim())
  if ((typeof page === 'string' && page.trim()) || typeof page === 'number') query.set('page', String(page))
  return `app://file/open?${query.toString()}`
}
