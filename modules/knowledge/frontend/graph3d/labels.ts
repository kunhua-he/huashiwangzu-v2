/**
 * Node labels: CSS2DRenderer overlay labels with distance-based visibility.
 *
 * Labels are HTML spans positioned via CSS2DRenderer.
 * Visibility toggles based on camera distance to avoid occlusion at long range.
 */

/// <reference path="./three.d.ts" />

import { THREE, CSS2DRenderer, CSS2DObject } from './three-addons'
import { theme } from './theme'
import type { GraphNode } from './types'
import type { LayoutPosition } from './layout3d'

/** Label rendering context */
export interface LabelRenderContext {
  renderer: CSS2DRenderer
  labels: Map<number, CSS2DObject>
  showLabels: (threshold: number) => void
  updatePositions: (positions: Map<number, LayoutPosition>) => void
  dispose: () => void
}

/** Create label renderer and populate labels */
export function buildLabels(
  nodes: GraphNode[],
  positions: Map<number, LayoutPosition>,
  container: HTMLElement,
): LabelRenderContext {
  // ── CSS2DRenderer ──
  const renderer = new CSS2DRenderer()
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.domElement.style.position = 'absolute'
  renderer.domElement.style.top = '0'
  renderer.domElement.style.left = '0'
  renderer.domElement.style.pointerEvents = 'none'
  container.appendChild(renderer.domElement)

  // ── Create label elements ──
  const labels = new Map<number, CSS2DObject>()

  for (const node of nodes) {
    const pos = positions.get(node.id)
    if (!pos) continue

    const div = document.createElement('div')
    div.textContent = node.label
    div.style.color = theme.text.starlight
    div.style.fontSize = '11px'
    div.style.fontFamily = '苹方, "微软雅黑", sans-serif'
    div.style.textShadow = '0 0 6px rgba(0,0,0,0.8)'
    div.style.whiteSpace = 'nowrap'
    div.style.pointerEvents = 'none'
    div.style.userSelect = 'none'
    div.style.transition = 'opacity 0.15s ease'

    const label = new CSS2DObject(div)
    label.position.set(pos.x, pos.y, pos.z)
    labels.set(node.id, label)
  }

  return {
    renderer,
    labels,

    /** Toggle label visibility based on camera-to-node distance threshold */
    showLabels(threshold: number) {
      for (const [id, label] of labels) {
        const pos = positions.get(id)
        if (!pos) continue
        const dist = Math.sqrt(pos.x * pos.x + pos.y * pos.y + pos.z * pos.z)
        label.element.style.opacity = dist > threshold ? '0' : '1'
      }
    },

    /** Reposition labels when layout changes */
    updatePositions(newPositions: Map<number, LayoutPosition>) {
      for (const [id, pos] of newPositions) {
        const label = labels.get(id)
        if (label) label.position.set(pos.x, pos.y, pos.z)
      }
    },

    dispose() {
      for (const label of labels.values()) {
        label.removeFromParent()
        label.element.remove()
      }
      labels.clear()
      renderer.domElement.remove()
      renderer.dispose()
    },
  }
}
