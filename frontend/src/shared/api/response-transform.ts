import { friendlyErrorMessage } from '@/shared/composables/use-friendly-error'

export function 获取错误信息(error: unknown) {
  const 响应错误 = error as { config?: { url?: string }; response?: { status?: number; data?: Record<string, unknown> } }
  const 状态码 = 响应错误.response?.status
  const 响应数据 = 响应错误.response?.data
  const 是登录请求 = 响应错误.config?.url?.endsWith('/login') === true
  if (!响应错误.response) return { success: false, 数据: null, error: '网络连接异常，请检查公司网络' }

  let 错误信息 = ''
  if (状态码 === 401 && 是登录请求) {
    错误信息 = friendlyErrorMessage((响应数据?.error as string) || '用户名或密码错误')
  } else if (状态码 === 401) {
    错误信息 = '登录已过期，请重新登录'
  } else if (状态码 === 403) {
    错误信息 = '你没有权限操作这个内容'
  } else if (状态码 === 404) {
    错误信息 = '内容不存在或已被删除'
  } else if (状态码 === 502) {
    错误信息 = '后端服务暂时不可用，请检查 scripts/start_backend.sh 是否已运行'
  } else if (状态码 && 状态码 >= 500) {
    错误信息 = '系统开小差了，请联系管理员'
  } else {
    错误信息 = friendlyErrorMessage((响应数据?.error as string) || '请求失败，请稍后重试')
  }
  return { success: false, 数据: 响应数据?.data ?? 响应数据?.data ?? null, error: 错误信息 }
}
