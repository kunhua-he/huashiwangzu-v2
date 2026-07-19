import type { Component } from 'vue'
import {
  AppWindow,
  Bot,
  BookOpen,
  Brain,
  Braces,
  Clock3,
  Compass,
  Database,
  FilePenLine,
  FileText,
  FolderOpen,
  Headphones,
  Image,
  Layers3,
  LayoutGrid,
  Mail,
  MessageCircle,
  Network,
  PenLine,
  Presentation,
  Route,
  ScanSearch,
  Search,
  Settings,
  Sparkles,
  SquareTerminal,
  Table2,
  Trash2,
  Video,
  WandSparkles,
  Wrench,
} from 'lucide-vue-next'

export type AppIconMaterial = 'glass' | 'metal' | 'paper' | 'plastic'

export interface AppIconProfile {
  key: string
  glyph: Component
  from: string
  to: string
  accent: string
  material?: AppIconMaterial
  depth?: string
}

const FALLBACK_PROFILE: AppIconProfile = {
  key: 'generic-app',
  glyph: AppWindow,
  from: '#8e8e93',
  to: '#48484a',
  accent: '#ffffff',
  material: 'plastic',
}

const APP_PROFILES: Record<string, AppIconProfile> = {
  /* accent 用白/浅色线标，对齐系统 Dock 渐变方块 */
  desktop: { key: 'finder', glyph: FolderOpen, from: '#5ec9f8', to: '#1463e8', accent: '#ffffff', material: 'glass' },
  files: { key: 'files', glyph: FolderOpen, from: '#5ec9f8', to: '#1463e8', accent: '#ffffff', material: 'glass' },
  recycle: { key: 'trash', glyph: Trash2, from: '#f0f0f5', to: '#d2d2dc', accent: '#636366', material: 'metal' },
  agent: { key: 'ai-assistant', glyph: Bot, from: '#8b6cff', to: '#3b2bb5', accent: '#ffffff', material: 'glass' },
  ai: { key: 'ai-product', glyph: Bot, from: '#8b6cff', to: '#3b2bb5', accent: '#ffffff', material: 'glass' },
  knowledge: { key: 'knowledge', glyph: BookOpen, from: '#34d3aa', to: '#0b8f7d', accent: '#ffffff', material: 'paper' },
  memory: { key: 'memory', glyph: Brain, from: '#f472b6', to: '#9d174d', accent: '#ffffff', material: 'glass' },
  office: { key: 'office', glyph: FileText, from: '#60a5fa', to: '#1d4ed8', accent: '#ffffff', material: 'paper' },
  text: { key: 'text', glyph: FilePenLine, from: '#ffe57a', to: '#ffc600', accent: '#ffffff', material: 'paper' },
  media: { key: 'media', glyph: Video, from: '#7bf87b', to: '#0fd130', accent: '#ffffff', material: 'glass' },
  messages: { key: 'messages-product', glyph: MessageCircle, from: '#7bf87b', to: '#0fd130', accent: '#ffffff', material: 'glass' },
  settings: { key: 'settings-product', glyph: Settings, from: '#8e8e93', to: '#48484a', accent: '#ffffff', material: 'metal' },
  'content-studio': { key: 'content-studio-product', glyph: Layers3, from: '#38bdf8', to: '#4338ca', accent: '#ffffff', material: 'glass' },
  launchpad: { key: 'launchpad', glyph: LayoutGrid, from: '#8e8e93', to: '#48484a', accent: '#ffffff', material: 'metal' },
  spotlight: { key: 'spotlight', glyph: Search, from: '#8e8e93', to: '#48484a', accent: '#ffffff', material: 'metal' },
  'mission-control': { key: 'mission-control', glyph: Layers3, from: '#5ec9f8', to: '#1463e8', accent: '#ffffff', material: 'glass' },
  'model-router': { key: 'model-router', glyph: Route, from: '#27364b', to: '#111827', accent: '#ffffff', material: 'metal' },
  'douyin-delivery': { key: 'content-studio', glyph: Video, from: '#ff416c', to: '#161a2c', accent: '#ffffff', material: 'glass' },
  'image-viewer': { key: 'image-viewer', glyph: Image, from: '#38bdf8', to: '#2563eb', accent: '#ffffff', material: 'glass' },
  'image-vision': { key: 'image-vision', glyph: ScanSearch, from: '#2dd4bf', to: '#0f766e', accent: '#ffffff', material: 'glass' },
  'image-gen': { key: 'image-generation', glyph: WandSparkles, from: '#f472b6', to: '#7c3aed', accent: '#ffffff', material: 'glass' },
  'pdf-viewer': { key: 'pdf-viewer', glyph: FileText, from: '#f87171', to: '#b91c1c', accent: '#ffffff', material: 'paper' },
  'doc-viewer': { key: 'document-viewer', glyph: FileText, from: '#60a5fa', to: '#1d4ed8', accent: '#ffffff', material: 'paper' },
  'text-editor': { key: 'text-editor', glyph: FilePenLine, from: '#94a3b8', to: '#334155', accent: '#ffffff', material: 'paper' },
  'excel-engine': { key: 'spreadsheet', glyph: Table2, from: '#34d399', to: '#047857', accent: '#ffffff', material: 'paper' },
  'ppt-viewer': { key: 'presentation', glyph: Presentation, from: '#fb923c', to: '#c2410c', accent: '#ffffff', material: 'paper' },
  im: { key: 'messages', glyph: MessageCircle, from: '#4ade80', to: '#15803d', accent: '#ffffff', material: 'glass' },
  'docs-open': { key: 'docs-open', glyph: Braces, from: '#22d3ee', to: '#155e75', accent: '#ffffff', material: 'metal' },
  'wechat-writer': { key: 'wechat-writer', glyph: PenLine, from: '#4ade80', to: '#047857', accent: '#ffffff', material: 'paper' },
  'media-intelligence': { key: 'media-intelligence', glyph: Headphones, from: '#a78bfa', to: '#4338ca', accent: '#ffffff', material: 'glass' },
  'media-asr': { key: 'media-asr', glyph: Headphones, from: '#818cf8', to: '#3730a3', accent: '#ffffff', material: 'glass' },
  'terminal-tools': { key: 'terminal', glyph: SquareTerminal, from: '#475569', to: '#0f172a', accent: '#ffffff', material: 'metal' },
  'browser-tools': { key: 'browser', glyph: Compass, from: '#5ec9f8', to: '#1a6cf0', accent: '#ffffff', material: 'glass' },
  'web-tools': { key: 'web-search', glyph: Search, from: '#22d3ee', to: '#0e7490', accent: '#ffffff', material: 'glass' },
  'github-search': { key: 'code-search', glyph: Search, from: '#64748b', to: '#111827', accent: '#ffffff', material: 'metal' },
  scheduler: { key: 'scheduler', glyph: Clock3, from: '#fbbf24', to: '#b45309', accent: '#ffffff', material: 'plastic' },
  codemap: { key: 'codemap', glyph: Network, from: '#818cf8', to: '#312e81', accent: '#ffffff', material: 'glass' },
  'desktop-tools': { key: 'desktop-tools', glyph: Wrench, from: '#94a3b8', to: '#334155', accent: '#ffffff', material: 'metal' },
  'email-parser': { key: 'email', glyph: Mail, from: '#5ec9f8', to: '#1463e8', accent: '#ffffff', material: 'paper' },
  'office-gen': { key: 'office-generator', glyph: Sparkles, from: '#38bdf8', to: '#4338ca', accent: '#ffffff', material: 'glass' },
  'structured-parser': { key: 'structured-data', glyph: Database, from: '#2dd4bf', to: '#0f766e', accent: '#ffffff', material: 'metal' },
  'desktop-settings': { key: 'settings', glyph: Settings, from: '#8e8e93', to: '#48484a', accent: '#ffffff', material: 'metal' },
}

const ICON_PROFILES: Record<string, AppIconProfile> = {
  Files: APP_PROFILES.desktop,
  FolderOpened: APP_PROFILES.desktop,
  Delete: APP_PROFILES.recycle,
  ChatDotRound: APP_PROFILES.agent,
  Collection: APP_PROFILES.knowledge,
  Connection: APP_PROFILES['model-router'],
  VideoPlay: APP_PROFILES['douyin-delivery'],
  Grid: APP_PROFILES['excel-engine'],
  Document: APP_PROFILES['doc-viewer'],
  DocumentCopy: { key: 'documents', glyph: Layers3, from: '#3b82f6', to: '#3730a3', accent: '#ffffff' },
  Layers: APP_PROFILES['mission-control'],
  View: APP_PROFILES['image-viewer'],
  EditPen: APP_PROFILES['wechat-writer'],
  Message: APP_PROFILES['email-parser'],
  Monitor: APP_PROFILES['terminal-tools'],
  Globe: APP_PROFILES['browser-tools'],
  Search: APP_PROFILES['web-tools'],
  Timer: APP_PROFILES.scheduler,
  DataBoard: APP_PROFILES.codemap,
  Setting: APP_PROFILES['desktop-settings'],
}

export function getAppIconProfile(appKey?: string, icon?: string): AppIconProfile {
  if (appKey && APP_PROFILES[appKey]) {
    const profile = APP_PROFILES[appKey]
    return { material: 'plastic', depth: 'rgba(15,23,42,.22)', ...profile }
  }
  if (icon && ICON_PROFILES[icon]) {
    const profile = ICON_PROFILES[icon]
    return { material: 'plastic', depth: 'rgba(15,23,42,.22)', ...profile }
  }
  return FALLBACK_PROFILE
}
