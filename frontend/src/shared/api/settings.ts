import api from './index'
import type { ApiResponse, SystemConfig, RoleMatrixItem } from './types'

type ApiResponseWithData<T> = Omit<ApiResponse<T>, 'data'> & { data: T }

interface BackendUser {
  id: number
  username: string
  display_name: string
  email: string | null
  role: string
  enabled: boolean
  last_login: string | null
  created_at: string
}

interface BackendUserSearchResponse {
  users: BackendUser[]
  total: number
  keyword: string
}

interface BackendRoleMatrixItem {
  role_key: string
  display_name: string
  permissions: {
    user_management?: boolean
    system_config?: boolean
    role_matrix?: boolean
  }
}

interface BackendRoleMatrixResponse {
  matrix: BackendRoleMatrixItem[]
}

export interface UserEntry {
  id: number
  username: string
  displayName: string
  email: string
  role: string
  status: number
  createdAt: string
  lastLogin: string
}

export interface UserListResponse {
  userList: UserEntry[]
  total: number
}

function toUserEntry(user: BackendUser): UserEntry {
  return {
    id: user.id,
    username: user.username,
    displayName: user.display_name,
    email: user.email ?? '',
    role: user.role,
    status: user.enabled ? 1 : 0,
    createdAt: user.created_at,
    lastLogin: user.last_login ?? '',
  }
}

function toUserListResponse(users: BackendUser[], total = users.length): ApiResponseWithData<UserListResponse> {
  return {
    success: true,
    data: { userList: users.map(toUserEntry), total },
    error: null,
  }
}

function toRoleMatrixItem(item: BackendRoleMatrixItem): RoleMatrixItem {
  return {
    role: item.role_key,
    name: item.display_name,
    user_management: Boolean(item.permissions.user_management),
    system_config: Boolean(item.permissions.system_config),
    role_matrix: Boolean(item.permissions.role_matrix),
  }
}

function toRoleMatrixOutput(matrix: RoleMatrixItem[]): BackendRoleMatrixResponse {
  return {
    matrix: matrix.map(item => ({
      role_key: item.role,
      display_name: item.name,
      permissions: {
        user_management: item.user_management,
        system_config: item.system_config,
        role_matrix: item.role_matrix,
      },
    })),
  }
}

export function fetchUserList() {
  return api.get<unknown, ApiResponse<BackendUser[]>>('/users/').then(response =>
    toUserListResponse(response.data ?? []),
  )
}

export function searchUsers(keyword: string) {
  return api.get<unknown, ApiResponse<BackendUserSearchResponse>>('/users/search', {
    params: { keyword },
  }).then(response => {
    const data = response.data
    return toUserListResponse(data?.users ?? [], data?.total ?? 0)
  })
}

export function createUser(params: {
  username: string
  password: string
  displayName?: string
  email?: string
  role?: string
}) {
  return api.post<unknown, ApiResponse<BackendUser>>('/users/', {
    username: params.username,
    password: params.password,
    display_name: params.displayName || params.username,
    email: params.email || '',
    role: params.role || 'viewer',
  }).then((response): ApiResponseWithData<{ message: string; newId?: number }> => ({
    success: response.success,
    data: { message: 'User created successfully', newId: response.data?.id },
    error: response.error,
  }))
}

export function editUser(params: {
  userId: number
  displayName?: string
  email?: string
  role?: string
  password?: string
}) {
  return api.put<unknown, ApiResponse<BackendUser>>(`/users/${params.userId}`, {
    display_name: params.displayName,
    email: params.email,
    role: params.role,
    password: params.password,
  }).then((response): ApiResponseWithData<{ message: string }> => ({
    success: response.success,
    data: { message: 'User edited successfully' },
    error: response.error,
  }))
}

export function toggleUserEnabled(userId: number) {
  return api.post<unknown, ApiResponse<{ message: string; enabled: boolean }>>(`/users/${userId}/toggle-enabled`)
    .then((response): ApiResponseWithData<{ message: string }> => ({
      success: response.success,
      data: { message: response.data?.message || 'Status updated' },
      error: response.error,
    }))
}

export function fetchSystemConfig() {
  return api.get<unknown, ApiResponse<SystemConfig>>('/settings/system-config')
    .then((response): ApiResponseWithData<SystemConfig> => ({
      ...response,
      data: response.data ?? {
        project_name: '',
        system_version: '',
        login_page_title: '',
        default_role: 'viewer',
      },
    }))
}

export function saveSystemConfig(params: SystemConfig) {
  return api.put<unknown, ApiResponse<SystemConfig>>('/settings/system-config', params)
    .then((response): ApiResponseWithData<{ message: string; config: SystemConfig }> => ({
      success: response.success,
      data: { message: 'System config saved', config: response.data ?? params },
      error: response.error,
    }))
}

export function fetchRoleMatrix() {
  return api.get<unknown, ApiResponse<BackendRoleMatrixResponse>>('/roles/matrix')
    .then((response): ApiResponseWithData<{ matrix: RoleMatrixItem[] }> => ({
      success: response.success,
      data: { matrix: (response.data?.matrix ?? []).map(toRoleMatrixItem) },
      error: response.error,
    }))
}

export function saveRoleMatrix(matrix: RoleMatrixItem[]) {
  return api.put<unknown, ApiResponse<BackendRoleMatrixResponse>>('/roles/matrix', toRoleMatrixOutput(matrix))
    .then((response): ApiResponseWithData<{ message: string; matrix: RoleMatrixItem[] }> => ({
      success: response.success,
      data: {
        message: 'Role matrix saved',
        matrix: (response.data?.matrix ?? []).map(toRoleMatrixItem),
      },
      error: response.error,
    }))
}
