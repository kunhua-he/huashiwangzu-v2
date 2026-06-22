import api from './index'
import type { LoginParams, UserInfo } from './types'

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

export function loginRequest(params: LoginParams) {
  return api.post<unknown, LoginResponse>('/login', params)
}

export function fetchCurrentUser() {
  return api.get<unknown, UserInfo>('/current-user')
}

export function logoutRequest() {
  return api.post<unknown, null>('/logout')
}
