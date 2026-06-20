/**
 * Deep-space HUD color theme — HoloGram-compatible token palette.
 *
 * All visual tokens live here so the engine can be re-themed by swapping this file.
 */

import { NodeType } from './types'

/** Color hex string */
export type HexColor = string

/** RGBA string */
export type RGBAColor = string

/** A semantic color token set */
export interface ColorToken {
  hex: HexColor
  bright?: HexColor
  glow: RGBAColor
}

/** Theme palette — every visual constant */
export interface ThemePalette {
  /** Background colors */
  bg: {
    void: HexColor
    voidDeep: HexColor
  }
  /** Text / UI */
  text: {
    starlight: HexColor
    muted: HexColor
  }
  /** Node type colors */
  node: {
    subject: ColorToken      // 金 sol
    concept: ColorToken      // 蓝 signal
    tag: ColorToken          // 紫 nebula
    brand: ColorToken        // 亮蓝 signal-bright
    document: ColorToken     // 星光白 starlight
    unknown: ColorToken
  }
  /** Edge colors */
  edge: {
    strong: RGBAColor
    weak: RGBAColor
    neutral: RGBAColor
  }
  /** Panels */
  panel: {
    bg: RGBAColor
    edge: RGBAColor
    blur: string
  }
  /** Status */
  status: {
    error: HexColor
    warning: HexColor
    success: HexColor
  }
  /** Atmosphere */
  atmosphere: {
    scanlineOpacity: number
    vignetteColor: RGBAColor
  }
}

/** Full theme palette */
export const theme: ThemePalette = {
  bg: {
    void: '#030812',
    voidDeep: '#010408',
  },
  text: {
    starlight: '#e2edff',
    muted: '#7c8da0',
  },
  node: {
    subject: { hex: '#f0b848', bright: '#ffcc60', glow: 'rgba(240,170,50,0.30)' },
    concept: { hex: '#68a8ff', bright: '#8cc4ff', glow: 'rgba(80,140,240,0.35)' },
    tag: { hex: '#a088e0', bright: '#c0a8ff', glow: 'rgba(140,110,220,0.25)' },
    brand: { hex: '#8cc4ff', bright: '#b0dcff', glow: 'rgba(100,180,255,0.30)' },
    document: { hex: '#e2edff', bright: '#ffffff', glow: 'rgba(200,220,240,0.15)' },
    unknown: { hex: '#8aa0b5', bright: '#aab8c6', glow: 'rgba(100,120,140,0.15)' },
  },
  edge: {
    strong: 'rgba(104,168,255,0.55)',
    weak: 'rgba(104,168,255,0.12)',
    neutral: 'rgba(104,168,255,0.28)',
  },
  panel: {
    bg: 'rgba(4,12,28,0.92)',
    edge: 'rgba(54,82,128,0.28)',
    blur: 'blur(14px)',
  },
  status: {
    error: '#f04848',
    warning: '#f07838',
    success: '#48cc68',
  },
  atmosphere: {
    scanlineOpacity: 0.018,
    vignetteColor: 'rgba(1,4,8,0.60)',
  },
}

/** Default node type → visual mapping */
export const nodeTypeVisualMap: Record<string, { color: ColorToken; baseRadius: number }> = {
  [NodeType.Subject]: { color: theme.node.subject, baseRadius: 22 },
  [NodeType.Concept]: { color: theme.node.concept, baseRadius: 16 },
  [NodeType.Tag]: { color: theme.node.tag, baseRadius: 11 },
  [NodeType.Brand]: { color: theme.node.brand, baseRadius: 16 },
  [NodeType.Document]: { color: theme.node.document, baseRadius: 13 },
  [NodeType.Unknown]: { color: theme.node.unknown, baseRadius: 12 },
}

/** Get effective node radius by type and weight */
export function getNodeRadius(type: string, weight?: number, degree?: number): number {
  const entry = nodeTypeVisualMap[type] ?? nodeTypeVisualMap[NodeType.Unknown]
  const scale = 1 + Math.min((weight ?? 0) * 0.3 + (degree ?? 0) * 0.02, 1.5)
  return entry.baseRadius * scale
}

/** Get node color by type */
export function getNodeColor(type: string): ColorToken {
  return nodeTypeVisualMap[type]?.color ?? theme.node.unknown
}
