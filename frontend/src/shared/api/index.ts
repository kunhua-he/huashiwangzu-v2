import axios from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from './types'
import { getErrorInfo, toApiErrorInfo } from './response-transform'

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
const retriedRequests = new Set<string>()
const errorThrottle = new Map<string, number>()
const throttleInterval = 30000

function reportFrontendError(url: string, statusCode: number | undefined, errorMessage: string) {
  if (url.includes('/logs/frontend-error')) return
  void axios.post(`${API_BASE_URL}/logs/frontend-error`, {
    url, status_code: statusCode || 0, error_message: errorMessage, page_path: window.location.pathname,
  }, { withCredentials: true, timeout: 3000 }).catch(() => undefined)
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
    if (response.config?.responseType === 'blob') return response

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
      ElMessage.error(errInfo.userMessage)
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
      localStorage.removeItem(TOKEN_KEY)
      delete api.defaults.headers.common['Authorization']
      if (!retriedRequests.has(requestUrl)) {
        retriedRequests.add(requestUrl)
        await new Promise(r => setTimeout(r, 500))
        try {
          const res = await api.request(error.config)
          return res
        } catch {
          retriedRequests.delete(requestUrl)
          if (!redirectingToLogin) {
            redirectingToLogin = true
            window.location.replace('/')
            window.setTimeout(() => { redirectingToLogin = false }, 1000)
          }
          return Promise.reject(getErrorInfo(error))
        }
      }
      if (!redirectingToLogin) {
        redirectingToLogin = true
        window.location.replace('/')
        window.setTimeout(() => { redirectingToLogin = false }, 1000)
      }
    }
    if (statusCode === 403) ElMessage.error('你没有权限操作这个内容')
    const errorInfo = getErrorInfo(error)
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
