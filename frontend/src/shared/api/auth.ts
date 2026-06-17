import api from './index'
import type { ApiResponse, LoginParams, UserInfo } from './types'

export function loginRequest(params: LoginParams) {
  return api.post<unknown, ApiResponse<{ access_token: string; token_type: string; user: UserInfo }>>('/login', params)
}

export function fetchCurrentUser() {
  return api.get<unknown, ApiResponse<UserInfo>>('/current-user')
}

export function logoutRequest() {
  return api.post<unknown, ApiResponse<null>>('/logout')
}
