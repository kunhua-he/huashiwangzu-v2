import type { Component } from 'vue'

// 自动扫描 platform/components/apps/ 下所有 index.vue。
// 有组件才有映射，物理上不可能产生"假占位"——这是框架占位清零的根本保证。
const platformModules = import.meta.glob('/src/platform/components/apps/*/index.vue')

export const platformComponentKeyMap: Record<string, () => Promise<{ default: Component }>> = {}

for (const [filePath, loader] of Object.entries(platformModules)) {
  // filePath 形如：/src/platform/components/apps/desktop/index.vue
  const match = filePath.match(/apps\/([^/]+)\/index\.vue$/)
  if (match) {
    platformComponentKeyMap[`apps/${match[1]}/index.vue`] = loader as () => Promise<{ default: Component }>
  }
}
