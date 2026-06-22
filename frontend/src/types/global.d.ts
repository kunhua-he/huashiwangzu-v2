/**
 * Global window extensions shared across modules.
 * Declared here so all modules can access these properties
 * without `window as any` casts.
 */

export {}

declare global {
  interface Window {
    /** Payload from framework when opening a file module via <component v-bind="payload"> */
    __MODULE_OPEN_FILE_PAYLOAD__?: { fileId: number; fileName: string }

    /** Framework runtime config injected at page load */
    __HSWZ_CONFIG__?: { api_base_url?: string }

    /** Desktop platform bridge injected by the shell */
    platform?: {
      modules?: {
        openApp?: (appId: string, opts?: Record<string, unknown>) => void
      }
    }
  }
}
