export function formatFileDisplayName(fileName?: string | null, format?: string | null): string {
  const name = String(fileName || '')
  const ext = String(format || '').replace(/^\./, '')
  if (!name || !ext) return name
  return name.toLowerCase().endsWith(`.${ext.toLowerCase()}`) ? name : `${name}.${ext}`
}
