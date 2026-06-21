import { getApiUrl, hasPermission } from '../../_template/runtime/index'

export { getApiUrl, hasPermission }

export function getMode(): 'sandbox' | 'framework' {
  const meta = document.querySelector('meta[name="app-mode"]')
  return meta?.getAttribute('content') === 'framework' ? 'framework' : 'sandbox'
}

export function getModuleSetting(key: string): string | null {
  try {
    const el = document.querySelector(`meta[name="module-setting-${key}"]`)
    return el?.getAttribute('content') ?? null
  } catch {
    return null
  }
}
