export interface DesktopFileOpenPayload {
  fileId: number
  fileName?: string
  format?: string
  page?: number
  mode?: 'view' | 'edit'
}

interface DesktopClientAction {
  type?: unknown
  payload?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function normalizePayload(value: unknown): DesktopFileOpenPayload | null {
  if (!isRecord(value)) return null
  const fileId = Number(value.fileId ?? value.file_id)
  if (!Number.isInteger(fileId) || fileId <= 0) return null

  const pageRaw = value.page
  const page = pageRaw === undefined || pageRaw === null || pageRaw === ''
    ? undefined
    : Number(pageRaw)
  const mode = value.mode === 'edit' ? 'edit' : 'view'

  return {
    fileId,
    fileName: String(value.fileName ?? value.file_name ?? ''),
    format: String(value.format ?? value.extension ?? ''),
    page: Number.isInteger(page) && Number(page) > 0 ? Number(page) : undefined,
    mode,
  }
}

function resultPayload(result: unknown): unknown {
  if (!isRecord(result)) return result
  return isRecord(result.data) ? result.data : result
}

export function parseDesktopFileOpenUrl(url: string): DesktopFileOpenPayload | null {
  if (!url.startsWith('app://file/open')) return null
  try {
    const parsed = new URL(url)
    return normalizePayload({
      fileId: parsed.searchParams.get('file_id') || parsed.searchParams.get('fileId'),
      fileName: parsed.searchParams.get('file_name') || parsed.searchParams.get('fileName') || '',
      format: parsed.searchParams.get('format') || '',
      page: parsed.searchParams.get('page') || undefined,
    })
  } catch {
    return null
  }
}

export function openDesktopFile(payload: DesktopFileOpenPayload): boolean {
  if (!payload.fileId) return false
  const eventPayload: Record<string, unknown> = {
    fileId: payload.fileId,
    fileName: payload.fileName || '',
    format: payload.format || '',
  }
  if (payload.page !== undefined) eventPayload.page = payload.page
  if (payload.mode) eventPayload.mode = payload.mode

  if (window.__DESKTOP_EVENT_BUS__) {
    window.__DESKTOP_EVENT_BUS__.emit('file:open', eventPayload)
  } else {
    window.dispatchEvent(new CustomEvent('desktop:open-file', { detail: eventPayload }))
  }
  return true
}

export function openDesktopFileUrl(url: string): boolean {
  const payload = parseDesktopFileOpenUrl(url)
  return payload ? openDesktopFile(payload) : false
}

export function openDesktopFileAction(action: unknown): boolean {
  if (!isRecord(action)) return false
  const clientAction = action as DesktopClientAction
  if (clientAction.type !== 'open_file') return false
  const payload = normalizePayload(clientAction.payload)
  return payload ? openDesktopFile(payload) : false
}

export function openDesktopFileFromToolResult(result: unknown): boolean {
  const payload = resultPayload(result)
  if (!isRecord(payload)) return false
  if (openDesktopFileAction(payload.client_action)) return true
  const openUrl = typeof payload.open_url === 'string' ? payload.open_url : ''
  if (openUrl && openDesktopFileUrl(openUrl)) return true
  const directPayload = normalizePayload(payload)
  return directPayload ? openDesktopFile(directPayload) : false
}
