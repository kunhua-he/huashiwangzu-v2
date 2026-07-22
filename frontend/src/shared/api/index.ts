import axios from 'axios'
import { desktopMessage } from '@/desktop/feedback/desktop-feedback'
import type { ApiResponse } from './types'
import { getErrorInfo, markApiErrorNotified, toApiErrorInfo } from './response-transform'

const TOKEN_KEY = 'v2_auth_token'

export const API_BASE_URL = import.meta.env.VITE_API_BASE || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

const savedToken = localStorage.getItem(TOKEN_KEY)
if (savedToken) {
  api.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let redirectingToLogin = false
const retryingRequests = new Set<string>()
const errorThrottle = new Map<string, number>()
const throttleInterval = 30000

function getAuthorizationHeader(headers: unknown): string {
  if (!headers || typeof headers !== 'object') return ''
  const headerGetter = (headers as { get?: (name: string) => unknown }).get
  if (typeof headerGetter === 'function') {
    const value = headerGetter.call(headers, 'Authorization') ?? headerGetter.call(headers, 'authorization')
    return typeof value === 'string' ? value : ''
  }
  const record = headers as Record<string, unknown>
  const value = record.Authorization ?? record.authorization
  return typeof value === 'string' ? value : ''
}

function setAuthorizationHeader(config: { headers?: unknown }, token: string): void {
  const value = `Bearer ${token}`
  const headers = config.headers
  if (headers && typeof headers === 'object') {
    const headerSetter = (headers as { set?: (name: string, value: string) => void }).set
    if (typeof headerSetter === 'function') {
      headerSetter.call(headers, 'Authorization', value)
      return
    }
  }
  config.headers = { ...((headers as Record<string, unknown> | undefined) || {}), Authorization: value }
}

function reportFrontendError(url: string, statusCode: number | undefined, errorMessage: string) {
  if (url.includes('/logs/frontend-error')) return
  const token = localStorage.getItem(TOKEN_KEY)
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  void axios.post(`${API_BASE_URL}/logs/frontend-error`, {
    url, status_code: statusCode || 0, error_message: errorMessage, page_path: window.location.pathname,
  }, { withCredentials: true, timeout: 3000, headers }).catch(() => undefined)
}

function logErrorWithThrottle(url: string, statusCode: number | undefined, errorMessage: string) {
  const key = `${url}|${statusCode}`
  const lastReportedAt = errorThrottle.get(key) || 0
  const now = Date.now()
  if (now - lastReportedAt > throttleInterval) {
    errorThrottle.set(key, now)
    console.error(`[API] ${statusCode || '网络异常'} ${url} — ${errorMessage}`)
    reportFrontendError(url, statusCode, errorMessage)
  }
}

api.interceptors.response.use(
  (response) => {
    const responseData = response.data
    if (response.config?.responseType === 'blob') return responseData as unknown

    if (responseData?.data?.access_token) {
      const payload = responseData.data
      localStorage.setItem(TOKEN_KEY, payload.access_token)
      api.defaults.headers.common['Authorization'] = `Bearer ${payload.access_token}`
      return { user: payload.user || null, access_token: payload.access_token, token_type: payload.token_type }
    }

    if (responseData?.success === true) {
      return responseData.data as unknown
    }

    if (responseData?.success === false) {
      const errInfo = toApiErrorInfo({
        config: response.config,
        response: { status: response.status, data: responseData },
      })
      // Keep one desktop toast channel (not Element Plus) for uncaught API failures.
      desktopMessage.error(errInfo.userMessage)
      markApiErrorNotified(errInfo)
      logErrorWithThrottle(response.config?.url || '未知', response.status, errInfo.backendMessage || errInfo.userMessage)
      return Promise.reject(errInfo)
    }

    return responseData
  },
  async (error) => {
    const statusCode = error.response?.status
    const requestUrl = error.config?.url
    const isLoginRequest = requestUrl?.endsWith('/login') === true
    const currentPath = window.location.pathname
    const alreadyOnLoginPage = currentPath === '/' || currentPath === '/login'

    if (statusCode === 401 && !isLoginRequest && !alreadyOnLoginPage) {
      const currentToken = localStorage.getItem(TOKEN_KEY)
      const requestAuth = getAuthorizationHeader(error.config?.headers)
      const requestToken = requestAuth.startsWith('Bearer ') ? requestAuth.slice(7) : ''
      if (currentToken && requestToken && currentToken !== requestToken && error.config) {
        setAuthorizationHeader(error.config, currentToken)
        api.defaults.headers.common['Authorization'] = `Bearer ${currentToken}`
        try {
          return await api.request(error.config)
        } catch {
          // Fall through to the normal expired-session path if the fresh token also fails.
        }
      }
      localStorage.removeItem(TOKEN_KEY)
      delete api.defaults.headers.common['Authorization']
      const retryKey = `${error.config?.method || 'get'}:${requestUrl || ''}`
      if (!retryingRequests.has(retryKey)) {
        retryingRequests.add(retryKey)
        await new Promise(r => setTimeout(r, 500))
        try {
          const res = await api.request(error.config)
          return res
        } catch {
          if (!redirectingToLogin) {
            redirectingToLogin = true
            window.location.replace('/')
            window.setTimeout(() => { redirectingToLogin = false }, 1000)
          }
          return Promise.reject(getErrorInfo(error))
        } finally {
          retryingRequests.delete(retryKey)
        }
      }
      if (!redirectingToLogin) {
        redirectingToLogin = true
        window.location.replace('/')
        window.setTimeout(() => { redirectingToLogin = false }, 1000)
      }
    }
    const errorInfo = getErrorInfo(error)
    // 401 redirect path already handles session expiry; still surface other failures.
    if (statusCode !== 401) {
      desktopMessage.error(errorInfo.userMessage)
      markApiErrorNotified(errorInfo)
    }
    logErrorWithThrottle(requestUrl || '未知', statusCode, errorInfo.error || '未知错误')
    return Promise.reject(errorInfo)
  }
)

export function keepaliveFetch(url: string, body: unknown): void {
  const token = localStorage.getItem(TOKEN_KEY)
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  void fetch(`${API_BASE_URL}${url}`, {
    method: 'POST', credentials: 'include', keepalive: true,
    headers,
    body: JSON.stringify(body),
  })
}

export default api
export type { ApiResponse } from './types'
