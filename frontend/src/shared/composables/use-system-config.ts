import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSystemConfig, saveSystemConfig } from '@/shared/api/settings'
import type { SystemConfig } from '@/shared/api/types'

export function useSystemConfig() {
  const configSaving = ref(false)
  const configForm = ref<SystemConfig>({ project_name: '', system_version: '', login_page_title: '', default_role: 'viewer' })

  async function loadSystemConfig() {
    try { configForm.value = await fetchSystemConfig() }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Failed to load system config') }
  }

  async function systemConfigSave() {
    configSaving.value = true
    try { await saveSystemConfig(configForm.value); ElMessage.success('System config saved') }
    catch (e: unknown) { ElMessage.error((e as {error?: string})?.error || 'Save failed') }
    finally { configSaving.value = false }
  }

  onMounted(() => { loadSystemConfig() })

  return {
    configSaving, configForm, systemConfigSave, loadSystemConfig,
  }
}
