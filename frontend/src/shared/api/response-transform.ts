import { friendlyErrorMessage } from '@/shared/composables/use-friendly-error'

export type ApiErrorInfo = { success: false; data: null; error: string; http_status?: number }

export function getErrorInfo(error: unknown): ApiErrorInfo {
  const responseError = error as { config?: { url?: string }; response?: { status?: number; data?: Record<string, unknown> } }
  const statusCode = responseError.response?.status
  const responseData = responseError.response?.data
  const isLoginRequest = responseError.config?.url?.endsWith('/login') === true
  if (!responseError.response) return { success: false, data: null, error: '网络连接异常，请检查公司网络', http_status: 0 }

  let errorMessage = ''
  if (statusCode === 401 && isLoginRequest) {
    errorMessage = friendlyErrorMessage((responseData?.error as string) || '用户名或密码错误')
  } else if (statusCode === 401) {
    errorMessage = '登录已过期，请重新登录'
  } else if (statusCode === 403) {
    errorMessage = '你没有权限操作这个内容'
  } else if (statusCode === 404) {
    errorMessage = '内容不存在或已被删除'
  } else if (statusCode === 502) {
    errorMessage = '后端服务暂时不可用，请检查 scripts/start_backend.sh 是否已运行'
  } else if (statusCode && statusCode >= 500) {
    errorMessage = '系统开小差了，请联系管理员'
  } else {
    errorMessage = friendlyErrorMessage((responseData?.error as string) || '请求失败，请稍后重试')
  }
  return { success: false, data: null, error: errorMessage, http_status: statusCode }
}
