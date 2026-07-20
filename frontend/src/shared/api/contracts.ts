/**
 * Cross-runtime API contracts.
 *
 * This file intentionally has no Axios, Vue, or desktop dependencies so module
 * runtimes can reuse the same response shape in sandbox and framework builds.
 */
export interface ApiEnvelope<T = unknown> {
  success: boolean
  data?: T | null
  error?: string | null
  errors?: Record<string, string> | Array<{ field?: string; message: string }> | null
  code?: string | null
  message?: string | null
}

export interface ApiErrorPayload {
  error?: string | null
  message?: string | null
  detail?: string | Array<{ loc?: unknown[]; msg?: string; message?: string }> | null
  code?: string | null
  error_code?: string | null
  errors?: ApiEnvelope['errors']
}

export interface ApiErrorContract {
  success: false
  data: null
  error: string
  http_status?: number
  httpStatus?: number
  code?: string
  backendMessage?: string
  userMessage: string
  raw?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function isApiEnvelope<T = unknown>(value: unknown): value is ApiEnvelope<T> {
  return isRecord(value) && typeof value.success === 'boolean' && ('data' in value || 'error' in value)
}

export function getApiErrorMessage(payload: unknown, fallback = '请求失败'): string {
  if (!isRecord(payload)) return fallback

  const direct = [payload.error, payload.message, payload.detail]
    .find((value): value is string => typeof value === 'string' && value.trim().length > 0)
  if (direct) return direct

  const nestedError = payload.error
  if (isRecord(nestedError)) {
    const nestedMessage = [nestedError.message, nestedError.detail, nestedError.code]
      .find((value): value is string => typeof value === 'string' && value.trim().length > 0)
    if (nestedMessage) return nestedMessage
  }

  const errors = payload.errors
  if (Array.isArray(errors)) {
    const message = errors
      .map((item) => {
        if (!isRecord(item) || typeof item.message !== 'string') return ''
        return typeof item.field === 'string' && item.field ? `${item.field}: ${item.message}` : item.message
      })
      .filter(Boolean)
      .slice(0, 3)
      .join('；')
    if (message) return message
  } else if (isRecord(errors)) {
    const message = Object.entries(errors)
      .filter((entry): entry is [string, string] => typeof entry[1] === 'string' && entry[1].trim().length > 0)
      .slice(0, 3)
      .map(([field, value]) => `${field}: ${value}`)
      .join('；')
    if (message) return message
  }

  return fallback
}
