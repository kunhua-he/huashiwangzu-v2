/**
 * Global window extensions shared across modules.
 * Declared here so all modules can access these properties
 * without unsafe window casts.
 */

export {}

export interface PlatformCapability {
  module: string
  action: string
  description?: string
  parameters?: Record<string, unknown>
  min_role?: string
  brief?: string
}

export interface HuashiRuntimeConfig {
  mode: 'sandbox' | 'framework'
  api_base_url: string
  permissions: string[]
  module_settings: Record<string, unknown>
}

declare global {
  interface Window {
    /** Legacy config bag used by older pages; module runtime uses __HUASHI_RUNTIME__. */
    __HSWZ_CONFIG__?: { api_base_url?: string }

    /** Module runtime config injected by the desktop shell */
    __HUASHI_RUNTIME__?: HuashiRuntimeConfig

    /** Minimal standalone-module runtime config; full template runtimes use __HUASHI_RUNTIME__. */
    __MODULE_RUNTIME_CONFIG__?: HuashiRuntimeConfig

    /** Desktop platform bridge injected by the shell */
    platform?: {
      api?: {
	        request?: <T = unknown>(config: Record<string, unknown>) => Promise<T>
	        get?: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>
	        post?: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>
	        put?: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>
	        delete?: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>
	      }
      modules?: {
        call?: <T = unknown>(targetModule: string, action: string, parameters?: Record<string, unknown>) => Promise<T>
        capabilities?: () => Promise<PlatformCapability[]>
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
