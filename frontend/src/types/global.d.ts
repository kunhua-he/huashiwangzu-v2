/**
 * Global window extensions shared across modules.
 * Declared here so all modules can access these properties
 * without unsafe window casts.
 */

export {}

declare global {
  interface Window {
    /** Framework runtime config injected at page load */
    __HSWZ_CONFIG__?: { api_base_url?: string }

    /** Desktop platform bridge injected by the shell */
    platform?: {
      api?: {
        request?: <T = unknown>(config: Record<string, unknown>) => Promise<T>
        get?: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>
        post?: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>
      }
      modules?: {
        call?: <T = unknown>(targetModule: string, action: string, parameters?: Record<string, unknown>) => Promise<T>
        capabilities?: () => Promise<string[]>
        openApp?: (appId: string, opts?: Record<string, unknown>) => string | null
      }
    }

    /** Desktop event bus exposed for framework-integrated modules */
    __DESKTOP_EVENT_BUS__?: {
      emit: (name: string, payload: Record<string, unknown>) => void
    }
  }
}

declare module 'element-plus/dist/locale/zh-cn.mjs' {
  const zhCn: unknown
  export default zhCn
}
