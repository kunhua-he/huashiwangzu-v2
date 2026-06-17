import api from './index'
import type { ApiResponse, SystemConfig, RoleMatrixItem } from './types'

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

function toUserEntry(user: Record<string, unknown>): UserEntry {
  return {
    id: user.id as number,
    username: (user.username ?? user.username) as string,
    displayName: (user.displayName ?? user.display_name) as string,
    email: (user.email ?? user.email ?? '') as string,
    role: (user.role ?? user.role) as string,
    status: (user.status ?? (user.enabled === false ? 0 : 1)) as number,
    createdAt: (user.createdAt ?? user.created_at ?? '') as string,
    lastLogin: (user.lastLogin ?? user.last_login ?? '') as string,
  }
}

function toUserListResponse(response: Record<string, unknown>): { success: boolean; data: { userList: UserEntry[]; total: number }; error: string } {
  const data = (response as Record<string, unknown>).data ?? (response as Record<string, unknown>).data ?? response
  const rawList = (data as Record<string, unknown>)?.users ?? (data as Record<string, unknown>)?.['userList'] ?? []
  const list = Array.isArray(data) ? (data as Record<string, unknown>[]) : (rawList as Record<string, unknown>[])
  return { success: true, data: { userList: list.map(toUserEntry), total: ((data as Record<string, unknown>).total ?? list.length) as number }, error: '' }
}

function toSystemConfigInput(config: Record<string, unknown>): SystemConfig {
  return {
    project_name: (config.project_name ?? config.project_name ?? '') as string,
    system_version: (config.system_version ?? config.system_version ?? '') as string,
    login_page_title: (config.login_page_title ?? config.login_page_title ?? '') as string,
    default_role: (config.default_role ?? config.default_role ?? 'viewer') as string,
  }
}

function toSystemConfigOutput(config: SystemConfig): Record<string, string> {
  return {
    project_name: config.project_name,
    system_version: config.system_version,
    login_page_title: config.login_page_title,
    default_role: config.default_role,
  }
}

function toRoleMatrixItem(item: Record<string, unknown>): RoleMatrixItem {
  const perms = (item.permissions ?? (item as Record<string, unknown>).permissions ?? {}) as Record<string, unknown>
  return {
    role: (item.role ?? (item as Record<string, unknown>).role_key) as string,
    name: (item.name ?? (item as Record<string, unknown>).display_name) as string,
    user_management: !!(perms as Record<string, unknown>).user_management,
    system_config: !!(perms as Record<string, unknown>).system_config,
    role_matrix: !!(perms as Record<string, unknown>).role_matrix,
  }
}

function toRoleMatrixOutput(matrix: RoleMatrixItem[]) {
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
  return api.get('/users/').then(res => toUserListResponse(res as unknown as Record<string, unknown>))
}

export function searchUsers(keyword: string) {
  return api.get('/users/search', { params: { keyword } }).then(res => toUserListResponse(res as unknown as Record<string, unknown>))
}

export function createUser(params: {
  username: string
  password: string
  displayName?: string
  email?: string
  role?: string
}) {
  return api.post('/users/', {
    username: params.username,
    password: params.password,
    display_name: params.displayName || params.username,
    email: params.email || '',
    role: params.role || 'viewer',
  }).then((res: unknown) => { const r = res as Record<string, unknown>; return { success: true, data: { message: 'User created successfully', newId: (r.data as Record<string, unknown>)?.id as number ?? undefined }, error: '' }; })
}

export function editUser(params: {
  userId: number
  displayName?: string
  email?: string
  role?: string
  password?: string
}) {
  return api.put(`/users/${params.userId}`, {
    display_name: params.displayName,
    email: params.email,
    role: params.role,
    password: params.password,
  }).then(() => ({ success: true, data: { message: 'User edited successfully' }, error: '' }))
}

export function toggleUserEnabled(userId: number) {
  return api.post(`/users/${userId}/toggle-enabled`).then(() => ({ success: true, data: { message: 'Status updated' }, error: '' }))
}

export function fetchSystemConfig() {
  return api.get('/settings/system-config').then((res: unknown) => {
    const r = res as Record<string, unknown>;
    return { success: true, data: toSystemConfigInput((r.data ?? {}) as Record<string, string>), error: '' };
  })
}

export function saveSystemConfig(params: SystemConfig) {
  return api.put('/settings/system-config', toSystemConfigOutput(params)).then((res: unknown) => {
    const r = res as Record<string, unknown>;
    return { success: true, data: { message: 'System config saved', config: toSystemConfigInput((r.data ?? {}) as Record<string, string>) }, error: '' };
  })
}

export function fetchRoleMatrix() {
  return api.get('/roles/matrix').then((res: unknown) => {
    const r = res as Record<string, unknown>;
    return { success: true, data: { matrix: (((r.data as Record<string, unknown>)?.matrix || []) as Record<string, unknown>[]).map(toRoleMatrixItem) }, error: '' };
  })
}

export function saveRoleMatrix(matrix: RoleMatrixItem[]) {
  return api.put('/roles/matrix', toRoleMatrixOutput(matrix)).then((res: unknown) => {
    const r = res as Record<string, unknown>;
    return { success: true, data: { message: 'Role matrix saved', matrix: (((r.data as Record<string, unknown>)?.matrix || []) as Record<string, unknown>[]).map(toRoleMatrixItem) }, error: '' };
  })
}
