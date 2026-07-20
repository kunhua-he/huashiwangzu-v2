import type { Component } from 'vue'

/**
 * Icon boundary:
 * - AppIcon owns app/Dock/desktop product icons and may use native image assets.
 * - SystemIcon owns small actions, menus, states, and file-operation icons.
 * - Consumers should use semantic names below; legacy glyph aliases remain supported
 *   by SystemIcon while existing desktop menu data is migrated incrementally.
 */
export type SystemIconName =
  | 'archive'
  | 'check'
  | 'copy'
  | 'delete'
  | 'details'
  | 'download'
  | 'folder'
  | 'folder-open'
  | 'image'
  | 'list'
  | 'menu'
  | 'open'
  | 'refresh'
  | 'settings'
  | 'upload'

export type IconComponent = Component
