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

    /** Framework runtime context injected by the desktop shell */
    __HUASHI_RUNTIME__?: {
      mode: string
      api_base_url: string
      permissions: string[]
      module_settings: Record<string, string>
    }

    /** Window manager reference exposed to modules */
    __HSWZ_WINDOW_MANAGER__?: {
      openWindow: (appKey: string, payload?: Record<string, unknown>) => void
      closeWindow: (windowId: string) => void
      focusWindow: (windowId: string) => void
      minimizeWindow: (windowId: string) => void
    }

    /** Payload passed when opening a module from a file */
    __MODULE_OPEN_FILE_PAYLOAD__?: {
      fileId: number
      fileName: string
      format: string
      page?: number
    }

    /** Desktop platform bridge injected by the shell */
    platform?: {
      modules?: {
        openApp?: (appId: string, opts?: Record<string, unknown>) => void
      }
    }
  }
}
