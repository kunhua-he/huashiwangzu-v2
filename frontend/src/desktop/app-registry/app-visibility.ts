import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'

const WINDOW_TYPE_BACKGROUND_SERVICE = 'background-service'
const WINDOW_TYPE_BACKGROUND_ALIAS = 'background'

export function isDirectlyOpenableApp(app: AppRegistryEntry): boolean {
  return app.enabled !== false
    && app.windowType !== WINDOW_TYPE_BACKGROUND_SERVICE
    && app.windowType !== WINDOW_TYPE_BACKGROUND_ALIAS
}

export function isLauncherVisibleApp(app: AppRegistryEntry): boolean {
  return Boolean(app.showInLauncher) && isDirectlyOpenableApp(app)
}

export function isBackgroundCapabilityApp(app: AppRegistryEntry): boolean {
  return app.enabled !== false && !isDirectlyOpenableApp(app)
}

export const BACKGROUND_CAPABILITY_MESSAGE = '该能力是后台服务，不能直接打开窗口'

export function getOpenWindowFailureMessage(app?: AppRegistryEntry): string {
  if (!app) return '应用不存在或暂不可用'
  if (isBackgroundCapabilityApp(app)) return BACKGROUND_CAPABILITY_MESSAGE
  if (app.enabled === false) return `应用「${app.appName}」已停用`
  return `应用「${app.appName}」暂时无法打开`
}
