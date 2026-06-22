import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginRequest, fetchCurrentUser, logoutRequest } from '@/shared/api/auth'
import type { UserInfo, ApiResponse } from '@/shared/api/types'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null)
  const isLoggedIn = ref(false)
  const isLoading = ref(false)
  const hasChecked = ref(false)

  async function fetchCurrentUserAction() {
    if (hasChecked.value) return
    hasChecked.value = true
    isLoading.value = true
    try {
      const user = await fetchCurrentUser()
      if (isLoggedIn.value) return
      if (user != null) userInfo.value = user
      isLoggedIn.value = true
    } catch {
      userInfo.value = null
      isLoggedIn.value = false
    } finally {
      isLoading.value = false
    }
  }

  function resetCheck() {
    hasChecked.value = false
    userInfo.value = null
    isLoggedIn.value = false
  }

  async function login(username: string, password: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const loginData = await loginRequest({ username, password })
      if (loginData?.user) userInfo.value = loginData.user
      isLoggedIn.value = true
      return { success: true, data: loginData as unknown as Record<string, unknown>, error: null }
    } catch (e: unknown) {
      return { success: false, data: null, error: (e as {error?: string})?.error || '登录失败' }
    }
  }

  async function logout() {
    try {
      await logoutRequest()
    } catch {
      // ignore logout error
    }
    localStorage.removeItem('v2_auth_token')
    userInfo.value = null
    isLoggedIn.value = false
    hasChecked.value = false
  }

  return { userInfo, isLoggedIn, isLoading, hasChecked, fetchCurrentUser: fetchCurrentUserAction, resetCheck, login, logout }
})
