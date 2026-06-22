import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchUserList, searchUsers, createUser, editUser, toggleUserEnabled, fetchSystemConfig, saveSystemConfig, fetchRoleMatrix, saveRoleMatrix } from '@/shared/api/settings'
import type { UserEntry } from '@/shared/api/settings'
import type { SystemConfig, RoleMatrixItem } from '@/shared/api/types'
import { useAppStateSnapshot } from '@/desktop/window-manager/use-app-state-snapshot'

export function useSettings() {
  const activeTab = useAppStateSnapshot('settings', 'activeTab', 'userManagement')
  const userList = ref<UserEntry[]>([])
  const isLoading = ref(false)
  const searchQuery = ref('')
  const dialogVisible = ref(false)
  const dialogMode = ref<'new' | 'edit'>('new')
  const isSubmitting = ref(false)
  const editingTarget = ref<UserEntry | null>(null)
  const form = ref({ username: '', password: '', displayName: '', email: '', role: 'viewer' as string })
  const configSaving = ref(false)
  const matrixSaving = ref(false)
  const configForm = ref<SystemConfig>({ project_name: '', system_version: '', login_page_title: '', default_role: 'viewer' })
  const roleMatrix = ref<RoleMatrixItem[]>([])

  function roleLabel(role: string) { return { admin: 'Administrator', editor: 'Editor', viewer: 'Viewer' }[role] || role }
  function roleTagType(role: string) { return { admin: 'danger', editor: 'primary', viewer: 'info' }[role] || 'info' }

  async function loadUsers() {
    isLoading.value = true
    try { userList.value = (await fetchUserList()).userList }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Failed to load user list') }
    finally { isLoading.value = false }
  }

  async function executeSearch() {
    if (!searchQuery.value.trim()) { loadUsers(); return }
    isLoading.value = true
    try { userList.value = (await searchUsers(searchQuery.value.trim())).userList }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Search failed') }
    finally { isLoading.value = false }
  }

  function openDialog(mode: 'new' | 'edit', user?: UserEntry) {
    dialogMode.value = mode
    if (mode === 'edit' && user) {
      editingTarget.value = user
      form.value = { username: '', password: '', displayName: user.displayName || '', email: user.email || '', role: user.role || 'viewer' }
    } else { form.value = { username: '', password: '', displayName: '', email: '', role: 'viewer' } }
    dialogVisible.value = true
  }

  async function submitForm() {
    if (dialogMode.value === 'new') {
      if (!form.value.username || !form.value.password) { ElMessage.warning('Username and password are required'); return }
      isSubmitting.value = true
      try { await createUser(form.value); ElMessage.success('Created successfully'); dialogVisible.value = false; loadUsers() }
      catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Creation failed') }
      finally { isSubmitting.value = false }
    } else {
      isSubmitting.value = true
      try { await editUser({ userId: editingTarget.value!.id, displayName: form.value.displayName, email: form.value.email, role: form.value.role, password: form.value.password || undefined }); ElMessage.success(form.value.password ? 'Password has been reset. Please inform the user.' : 'Updated successfully'); dialogVisible.value = false; loadUsers() }
      catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Update failed') }
      finally { isSubmitting.value = false }
    }
  }

  async function toggleStatus(user: UserEntry) {
    const action = user.status === 1 ? 'disable' : 'enable'
    try { await ElMessageBox.confirm(`Confirm ${action} user "${user.username}"?`, 'Confirm') } catch { return }
    try {
      await toggleUserEnabled(user.id)
      ElMessage.success(`${action} successful`); loadUsers()
    } catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || `${action} failed`) }
  }

  async function loadSystemConfig() {
    try {
      configForm.value = await fetchSystemConfig()
    } catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Failed to load system config') }
  }

  async function systemConfigSave() {
    configSaving.value = true
    try { await saveSystemConfig(configForm.value); ElMessage.success('System config saved') }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Save failed') }
    finally { configSaving.value = false }
  }

  async function loadRoleMatrix() {
    try {
      roleMatrix.value = (await fetchRoleMatrix()).matrix
    } catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Failed to load role matrix') }
  }

  async function roleMatrixSave() {
    matrixSaving.value = true
    try { await saveRoleMatrix(roleMatrix.value); ElMessage.success('Role matrix saved') }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Save failed') }
    finally { matrixSaving.value = false }
  }

  onMounted(() => { loadUsers(); loadSystemConfig(); loadRoleMatrix() })

  return {
    activeTab, userList, isLoading, searchQuery, dialogVisible, dialogMode, isSubmitting, form, configSaving, matrixSaving, configForm, roleMatrix,
    roleLabel, roleTagType, loadUsers, executeSearch, openDialog, submitForm, toggleStatus, loadSystemConfig, systemConfigSave, loadRoleMatrix, roleMatrixSave,
  }
}
