import type { Component } from 'vue'
import { componentKeyMap as generatedMap } from './component-key-map.generated'

// Legacy Chinese entry_component_key → component loader mapping (V1→V2 compat layer)
// New apps should be added directly in component-key-map.generated.ts
const legacyKeyCompatMap: Record<string, string> = {
  '应用/core-system/入口.vue': 'apps/core-system/index.vue',
  '应用/app-manager/入口.vue': 'apps/app-manager/index.vue',
  '应用/dashboard/入口.vue': 'apps/dashboard/index.vue',
  '应用/desktop/入口.vue': 'apps/desktop/index.vue',
  '应用/recycle/入口.vue': 'apps/recycle/index.vue',
  '应用/textEditor/入口.vue': 'apps/textEditor/index.vue',
  '应用/filePreview/入口.vue': 'apps/filePreview/index.vue',
  '应用/file-toolbox/入口.vue': 'apps/file-toolbox/index.vue',
  '应用/docxEditor/入口.vue': 'apps/docxEditor/index.vue',
  '应用/office-workbench/入口.vue': 'apps/office-workbench/index.vue',
  '应用/pptxEditor/入口.vue': 'apps/pptxEditor/index.vue',
  '应用/excelEditor/入口.vue': 'apps/excelEditor/index.vue',
  '应用/csvEditor/入口.vue': 'apps/csvEditor/index.vue',
  '应用/user-admin/入口.vue': 'apps/user-admin/index.vue',
  '应用/role-matrix/入口.vue': 'apps/role-matrix/index.vue',
  '应用/system-config/入口.vue': 'apps/system-config/index.vue',
  '应用/system-logs/入口.vue': 'apps/system-logs/index.vue',
  '应用/backup-restore/入口.vue': 'apps/backup-restore/index.vue',
  '应用/system-status/入口.vue': 'apps/system-status/index.vue',
  '应用/feedback-center/入口.vue': 'apps/feedback-center/index.vue',
  '应用/maintenance-center/入口.vue': 'apps/maintenance-center/index.vue',
  '应用/settings/入口.vue': 'apps/settings/index.vue',
  '应用/notification-center/入口.vue': 'apps/notification-center/index.vue',
  '应用/tasks/入口.vue': 'apps/tasks/index.vue',
  '应用/agent/入口.vue': 'ai-assistant/index.vue',
  '应用/ai-toolbox/入口.vue': 'apps/ai-toolbox/index.vue',
  '应用/prompt-manager/入口.vue': 'apps/prompt-manager/index.vue',
  '应用/knowledge/入口.vue': 'apps/knowledge/index.vue',
  '应用/knowledge-toolbox/入口.vue': 'apps/knowledge-toolbox/index.vue',
  '应用/visual-extraction-console/入口.vue': 'apps/visual-extraction-console/index.vue',
}

export const componentKeyMap: Record<string, () => Promise<{ default: Component }>> = {
  ...generatedMap,
}

// Mount legacy Chinese keys onto componentKeyMap, mapping to the corresponding English key's loader
for (const [oldKey, newKey] of Object.entries(legacyKeyCompatMap)) {
  if (newKey && generatedMap[newKey]) {
    componentKeyMap[oldKey] = generatedMap[newKey]
  }
}
