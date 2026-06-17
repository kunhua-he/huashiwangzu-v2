import type { appId, CrossAppActionResponse, ActionHandlerDeclaration } from './types-app-handle-v2'

const handlerRegistry = new Map<appId, Map<string, ActionHandlerDeclaration['handler']>>()

export function registerActionHandler(decl: ActionHandlerDeclaration): void {
  if (!handlerRegistry.has(decl.appKey)) {
    handlerRegistry.set(decl.appKey, new Map())
  }
  handlerRegistry.get(decl.appKey)!.set(decl.action, decl.handler)
}

export function unregisterAppHandlers(appId: appId): void {
  handlerRegistry.delete(appId)
}

export function unregisterActionHandler(appId: appId, action: string): void {
  const appHandlers = handlerRegistry.get(appId)
  if (appHandlers) {
    appHandlers.delete(action)
    if (appHandlers.size === 0) {
      handlerRegistry.delete(appId)
    }
  }
}

export function getRegisteredAppIds(): appId[] {
  return Array.from(handlerRegistry.keys())
}

export function getRegisteredActions(appId: appId): string[] {
  const appHandlers = handlerRegistry.get(appId)
  return appHandlers ? Array.from(appHandlers.keys()) : []
}

export async function routeRequest(
  targetAppId: appId,
  action: string,
  params: Record<string, unknown>,
  metadata: { sourceAppId: appId; sourceWindowId: string; requestId: string }
): Promise<CrossAppActionResponse> {
  const appHandlers = handlerRegistry.get(targetAppId)
  if (!appHandlers) {
    return { success: false, error: { code: 'ERR_HANDLER_NOT_REGISTERED', message: `App ${targetAppId} has no registered handlers` } }
  }
  const handler = appHandlers.get(action)
  if (!handler) {
    return { success: false, error: { code: 'ERR_ACTION_NOT_PUBLIC', message: `App ${targetAppId} does not expose action ${action}` } }
  }
  return await handler(params, metadata)
}

export function isHandlerRegistered(targetAppId: appId, action: string): boolean {
  const appHandlers = handlerRegistry.get(targetAppId)
  return appHandlers ? appHandlers.has(action) : false
}
