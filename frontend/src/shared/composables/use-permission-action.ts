import { computed, reactive } from 'vue'
import { useUserStore } from '@/platform/stores/user'
import api from '@/shared/api/index'

const roleLevels: Record<string, number> = {
  viewer: 1,
  editor: 2,
  admin: 9,
}

interface PermissionDef {
  minRole: string
  scope: string
}

interface PermissionMatrixItem {
  action: string
  name: string
  scope: string
  minRole: string
}

const permissionRegistry = reactive(new Map<string, PermissionDef>())
let loaded = false
let loading = false
let loadPromise: Promise<void> | null = null

async function loadAllPermissionsFromBackend(): Promise<void> {
  if (loaded) return
  if (loading && loadPromise) {
    return loadPromise
  }
  if (loading) return

  loading = true
  loadPromise = (async () => {
    try {
      const response = await api.get<unknown, { matrix: Record<string, unknown>[] }>('/roles/matrix')
      const matrix = (response?.matrix || []) as Record<string, unknown>[]
      const list: PermissionMatrixItem[] = matrix.flatMap((role: Record<string, unknown>) =>
        Object.entries((role as Record<string, unknown>).permissions || {})
          .filter(([, enabled]) => enabled)
          .map(([action]) => ({
            action,
            name: action,
            scope: 'system',
            minRole: role.role_key as string,
          }))
      )
      permissionRegistry.clear()
      for (const item of list) {
        permissionRegistry.set(item.action, { minRole: item.minRole, scope: item.scope })
      }
      loaded = true
    } catch {
      console.warn('[Permission] Failed to load permission matrix; action checks will deny by default.')
    } finally {
      loading = false
    }
  })()

  return loadPromise
}

export async function checkPermissionAction(action: string): Promise<boolean> {
  const userStore = useUserStore()
  const role = userStore.userInfo?.role || 'viewer'
  if (role === 'admin') return true

  await loadAllPermissionsFromBackend()

  const def = permissionRegistry.get(action)
  if (!def) return false
  return (roleLevels[role] ?? 0) >= (roleLevels[def.minRole] ?? 0)
}

export function usePermissionAction() {
  const store = useUserStore()
  const currentRole = computed(() => store.userInfo?.role || 'viewer')

  async function canExecute(action: string): Promise<boolean> {
    if (currentRole.value === 'admin') return true

    await loadAllPermissionsFromBackend()

    const def = permissionRegistry.get(action)
    if (!def) return false
    return (roleLevels[currentRole.value] ?? 0) >= (roleLevels[def.minRole] ?? 0)
  }

  return { canExecute, currentRole }
}
