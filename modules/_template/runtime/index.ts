/**
 * Module Runtime — shared middle layer between sandbox and main framework.
 *
 * Each module copies this file into modules/{name}/runtime/index.ts.
 * All API paths, permissions, and settings are read through this layer,
 * so module code never hardcodes framework-specific values.
 *
 * Usage:
 *   import { getApiUrl, getModuleConfig, hasPermission } from '../runtime'
 */

// ── Type definitions ────────────────────────────────────────────────
export interface RuntimeConfig {
  mode: 'sandbox' | 'framework'
  api_base_url: string
  permissions: string[]
  module_settings: Record<string, unknown>
}

// ── Framework injection key ─────────────────────────────────────────
// In main framework, these are provided by the desktop shell.
// In sandbox, they come from runtime.config.json.
let _config: RuntimeConfig | null = null

// ── Sandbox config loader ───────────────────────────────────────────
async function loadSandboxConfig(): Promise<RuntimeConfig> {
  try {
    const res = await fetch('/runtime.config.json')
    if (res.ok) return await res.json()
  } catch { /* ignore */ }
  // Fallback defaults
  return {
    mode: 'sandbox',
    api_base_url: '/api',
    permissions: ['viewer'],
    module_settings: {},
  }
}

// ── Public API ──────────────────────────────────────────────────────

/**
 * Initialize the runtime. In sandbox mode, loads runtime.config.json.
 * In framework mode, the shell calls initFramework(config) before mounting.
 */
export async function initRuntime(moduleKey: string): Promise<RuntimeConfig> {
  if (_config) return _config

  // Detect sandbox: if we can reach runtime.config.json, we're in sandbox
  const isSandbox = !!(document.querySelector('.sandbox-badge'))
  if (isSandbox) {
    _config = await loadSandboxConfig()
  } else {
    // Framework mode: use defaults until shell calls initFrameworkRuntime()
    _config = {
      mode: 'framework',
      api_base_url: '/api',
      permissions: ['viewer'],
      module_settings: {},
    }
  }
  return _config
}

/**
 * Called by the main framework shell to inject framework configuration.
 */
export function initFrameworkRuntime(config: RuntimeConfig): void {
  _config = { ...config, mode: 'framework' }
}

/** Full URL for an API endpoint: `${api_base_url}/your/path` */
export function getApiUrl(path: string): string {
  const base = _config?.api_base_url ?? '/api'
  return `${base}${path}`
}

/** Current runtime mode */
export function getMode(): 'sandbox' | 'framework' {
  return _config?.mode ?? 'sandbox'
}

/** Check if a permission is granted */
export function hasPermission(permission: string): boolean {
  return _config?.permissions?.includes(permission) ?? false
}

/** Get module-specific settings */
export function getModuleSetting<T = unknown>(key: string, defaultValue?: T): T | undefined {
  return (_config?.module_settings?.[key] as T) ?? defaultValue
}

/** Get the full runtime config (read-only) */
export function getRuntimeConfig(): Readonly<RuntimeConfig> {
  if (!_config) throw new Error('Runtime not initialized. Call initRuntime() first.')
  return _config
}
