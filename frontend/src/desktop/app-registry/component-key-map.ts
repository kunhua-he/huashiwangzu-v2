import type { Component } from 'vue'
import { componentKeyMap as generatedMap } from './component-key-map.generated'

// Legacy Chinese entry_component_key → component loader mapping (V1→V2 compat layer)
// New apps should be added directly in component-key-map.generated.ts
const legacyKeyCompatMap: Record<string, string> = {
  '应用/agent/入口.vue': 'ai-assistant/index.vue',
  '应用/dashboard/入口.vue': '',
  '应用/desktop/入口.vue': '',
  '应用/knowledge/入口.vue': '',
  '应用/recycle/入口.vue': '',
  '应用/settings/入口.vue': '',
  '应用/tasks/入口.vue': '',
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
