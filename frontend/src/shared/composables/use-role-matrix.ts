import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchRoleMatrix, saveRoleMatrix } from '@/shared/api/settings'
import type { RoleMatrixItem } from '@/shared/api/types'

export function useRoleMatrix() {
  const matrixSaving = ref(false)
  const roleMatrix = ref<RoleMatrixItem[]>([])

  async function loadRoleMatrix() {
    try { const res = await fetchRoleMatrix(); if (res.success) roleMatrix.value = res.data.matrix }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Failed to load role matrix') }
  }

  async function roleMatrixSave() {
    matrixSaving.value = true
    try { const res = await saveRoleMatrix(roleMatrix.value); if (res.success) ElMessage.success('Role matrix saved'); else ElMessage.error(res.error || 'Save failed') }
    finally { matrixSaving.value = false }
  }

  onMounted(() => { loadRoleMatrix() })

  return {
    matrixSaving, roleMatrix, roleMatrixSave, loadRoleMatrix,
  }
}
