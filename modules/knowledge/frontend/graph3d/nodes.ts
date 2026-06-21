/**
 * Card-style node rendering: PlaneGeometry billboard cards with canvas-drawn rounded rect.
 *
 * Each node = a THREE.Mesh (PlaneGeometry) with a canvas texture showing:
 * - Dark frosted-glass rounded-rect background
 * - Category-color left edge bar
 * - Entity name text (bold, readable)
 * - Small type label
 * Cards always face the camera (billboard behavior in render loop).
 * Important nodes get larger cards; minor nodes get compact cards.
 */

/// <reference path="./three.d.ts" />

import { THREE } from './three-addons'
import { getNodeRadius, resolveNodeColor, type ColorToken, typeDisplayLabels, mapChineseCategory } from './theme'
import type { GraphNode, GraphEdge } from './types'
import type { LayoutPosition } from './layout3d'

export interface NodeRenderContext {
  cards: Map<number, { mesh: THREE.Mesh; canvas: HTMLCanvasElement; nodeId: number }>
  fadeTo: (nodeId: number, opacity: number) => void
  fadeAll: (opacity: number) => void
  updatePositions: (positions: Map<number, LayoutPosition>) => void
  dispose: () => void
}

// ── Card drawing constants ──
const CARD_W = 220
const CARD_H = 64
const RADIUS = 10
const PADDING = 10
const COLOR_BAR_W = 5
const FONT_STR = '14px bold 苹方, "微软雅黑", sans-serif'
const FONT_SUB = '10px 苹方, "微软雅黑", sans-serif'
const FONT_MINOR = '11px bold 苹方, "微软雅黑", sans-serif'

/** Draw a single card onto a canvas */
function drawCard(
  canvas: HTMLCanvasElement,
  label: string,
  typeLabel: string,
  color: ColorToken,
  compact: boolean,
): void {
  const ctx = canvas.getContext('2d')!
  const w = canvas.width
  const h = canvas.height

  ctx.clearRect(0, 0, w, h)

  // ── Shadow (drop shadow for depth) ──
  ctx.shadowColor = 'rgba(0,0,0,0.5)'
  ctx.shadowBlur = 8
  ctx.shadowOffsetY = 3

  // ── Card background (rounded rect, frosted glass style) ──
  roundRect(ctx, 0, 0, w, h, RADIUS)
  const bgGrad = ctx.createLinearGradient(0, 0, 0, h)
  bgGrad.addColorStop(0, 'rgba(10,20,40,0.92)')
  bgGrad.addColorStop(1, 'rgba(6,14,30,0.95)')
  ctx.fillStyle = bgGrad
  ctx.fill()

  // Reset shadow for content
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0
  ctx.shadowOffsetY = 0

  // ── Border ──
  roundRect(ctx, 0, 0, w, h, RADIUS)
  ctx.strokeStyle = color.hex + '44'
  ctx.lineWidth = 0.8
  ctx.stroke()

  // ── Color bar (left edge accent) ──
  roundRect(ctx, 1, 6, COLOR_BAR_W, h - 12, 3)
  ctx.fillStyle = color.hex
  ctx.fill()

  // ── Text content ──
  const textX = COLOR_BAR_W + PADDING + 4
  const textW = w - textX - PADDING

  if (compact) {
    // Compact card: just the label, large
    ctx.fillStyle = '#ffffff'
    ctx.font = FONT_MINOR
    ctx.textBaseline = 'middle'
    const nameY = h / 2
    truncateFill(ctx, label, textX, nameY, textW)
  } else {
    // Full card: name + type label
    ctx.fillStyle = '#ffffff'
    ctx.font = FONT_STR
    ctx.textBaseline = 'bottom'
    truncateFill(ctx, label, textX, h / 2 - 2, textW)

    ctx.fillStyle = color.hex + 'bb'
    ctx.font = FONT_SUB
    ctx.textBaseline = 'top'
    truncateFill(ctx, typeLabel, textX, h / 2 + 4, textW)
  }
}

/** Helper: draw a rounded-rect path */
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.arcTo(x + w, y, x + w, y + r, r)
  ctx.lineTo(x + w, y + h - r)
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r)
  ctx.lineTo(x + r, y + h)
  ctx.arcTo(x, y + h, x, y + h - r, r)
  ctx.lineTo(x, y + r)
  ctx.arcTo(x, y, x + r, y, r)
  ctx.closePath()
}

/** Fill text, truncating with ellipsis if too wide */
function truncateFill(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxW: number): void {
  const m = ctx.measureText(text)
  if (m.width <= maxW) {
    ctx.fillText(text, x, y)
  } else {
    let trunc = text
    while (trunc.length > 2 && ctx.measureText(trunc + '…').width > maxW) {
      trunc = trunc.slice(0, -1)
    }
    ctx.fillText(trunc + '…', x, y)
  }
}

export function buildNodes(
  nodes: GraphNode[],
  positions: Map<number, LayoutPosition>,
  scene: THREE.Scene,
  edges: GraphEdge[] = [],
): NodeRenderContext {
  const cards = new Map<number, { mesh: THREE.Mesh; canvas: HTMLCanvasElement; nodeId: number }>()

  if (nodes.length === 0) {
    return {
      cards,
      fadeTo() {},
      fadeAll() {},
      updatePositions() {},
      dispose() {},
    }
  }

  // Pre-compute degree
  const degreeMap = new Map<number, number>()
  for (const e of edges) {
    degreeMap.set(e.source, (degreeMap.get(e.source) ?? 0) + 1)
    degreeMap.set(e.target, (degreeMap.get(e.target) ?? 0) + 1)
  }

  for (const node of nodes) {
    const pos = positions.get(node.id)
    if (!pos) continue

    const degree = degreeMap.get(node.id) ?? 0
    const radius = getNodeRadius(node.type, node.weight, degree)
    const color = resolveNodeColor(node.type)

    // Card size depends on importance (degree + weight)
    const importance = degree + (node.weight ?? 0) * 2
    const compact = importance < 2

    const cw = compact ? 120 : CARD_W
    const ch = compact ? 36 : CARD_H
    const canvas = document.createElement('canvas')
    canvas.width = cw * 2 // 2x for retina clarity
    canvas.height = ch * 2
    canvas.style.width = cw + 'px'
    canvas.style.height = ch + 'px'

    // Get display label for the node type
    const typeLabel = getSimpleTypeLabel(node.type)

    drawCard(canvas, node.label, typeLabel, color, compact)

    const texture = new THREE.CanvasTexture(canvas)
    texture.needsUpdate = true

    const geo = new THREE.PlaneGeometry(radius * 0.7, radius * 0.7 * (ch / cw))
    const mat = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.set(pos.x, pos.y, pos.z)
    mesh.userData.nodeId = node.id
    scene.add(mesh)

    cards.set(node.id, { mesh, canvas, nodeId: node.id })
  }

  return {
    cards,

    fadeTo(nodeId: number, opacity: number) {
      const entry = cards.get(nodeId)
      if (entry) {
        entry.mesh.material.opacity = opacity
      }
    },

    fadeAll(opacity: number) {
      for (const entry of cards.values()) {
        entry.mesh.material.opacity = opacity
      }
    },

    updatePositions(newPositions: Map<number, LayoutPosition>) {
      for (const [id, pos] of newPositions) {
        const entry = cards.get(id)
        if (entry) {
          entry.mesh.position.set(pos.x, pos.y, pos.z)
        }
      }
    },

    dispose() {
      for (const entry of cards.values()) {
        scene.remove(entry.mesh)
        entry.mesh.geometry.dispose()
        entry.mesh.material.map?.dispose()
        entry.mesh.material.dispose()
      }
      cards.clear()
    },
  }
}

function getSimpleTypeLabel(type: string): string {
  if (typeDisplayLabels[type]) return typeDisplayLabels[type]
  const englishKey = mapChineseCategory(type)
  if (typeDisplayLabels[englishKey]) return typeDisplayLabels[englishKey]
  return type
}
