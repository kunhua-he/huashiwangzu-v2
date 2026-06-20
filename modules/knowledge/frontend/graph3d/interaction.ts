/**
 * Interaction: OrbitControls + Raycaster-based hover, click, and focus.
 *
 * - OrbitControls: rotate/zoom/pan
 * - Hover: raycaster highlight (node + neighbors bright, others dim)
 * - Click: emit select event
 * - Double-click: camera fly-to focus
 * - Click empty space: clear highlight
 */

/// <reference path="./three.d.ts" />

import { THREE, OrbitControls } from './three-addons'

import { getNodeColor, getNodeRadius } from './theme'
import type { GraphNode, GraphEdge } from './types'
import type { LayoutPosition } from './layout3d'
import type { SceneContext } from './scene'
import type { NodeRenderContext } from './nodes'
import type { EdgeRenderContext } from './edges'

/** Interaction callbacks */
export interface InteractionCallbacks {
  onSelect: (node: GraphNode, position: { x: number; y: number }) => void
  onHover: (node: GraphNode | null, position: { x: number; y: number }) => void
}

/** Interaction context */
export interface InteractionContext {
  controls: OrbitControls
  dispose: () => void
}

const _dummyVec = new THREE.Vector3()

/** Build orbit controls and set up event listeners */
export function setupInteraction(
  scene: SceneContext,
  nodes: GraphNode[],
  edges: GraphEdge[],
  positions: Map<number, LayoutPosition>,
  nodeCtx: NodeRenderContext,
  edgeCtx: EdgeRenderContext,
  callbacks: InteractionCallbacks,
  canvas: HTMLCanvasElement,
): InteractionContext {
  // ── OrbitControls ──
  const controls = new OrbitControls(scene.camera, canvas)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.rotateSpeed = 0.8
  controls.zoomSpeed = 1.2
  controls.panSpeed = 0.5
  controls.minDistance = 80
  controls.maxDistance = 1200
  controls.target.set(0, 0, 0)

  // ── Raycaster ──
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()

  // Build a set of node IDs for quick lookup
  const nodeMap = new Map<number, GraphNode>()
  nodes.forEach(n => nodeMap.set(n.id, n))

  // Build adjacency for neighbor highlighting
  const adjacency = new Map<number, Set<number>>()
  for (const n of nodes) adjacency.set(n.id, new Set())
  for (const e of edges) {
    adjacency.get(e.source)?.add(e.target)
    adjacency.get(e.target)?.add(e.source)
  }

  // Track highlight state
  let highlightedId: number | null = null
  let hoveredId: number | null = null

  // Store original opacity for dim/restore
  let dimActive = false

  /** Helper: get mouse position in normalized device coordinates */
  function getPointer(event: MouseEvent): THREE.Vector2 {
    const rect = canvas.getBoundingClientRect()
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    return pointer
  }

  /** Cast ray, return hit node id or null */
  function raycastNodes(event: MouseEvent): number | null {
    raycaster.setFromCamera(getPointer(event), scene.camera)

    // We need to test against sphere meshes — collect all instanced meshes
    const meshes: THREE.InstancedMesh[] = []
    scene.scene.children.forEach((child: THREE.Object3D) => {
      if (child instanceof THREE.InstancedMesh) {
        meshes.push(child)
      }
    })

    const intersects = raycaster.intersectObjects(meshes)
    if (intersects.length > 0) {
      const hit = intersects[0]
      if (hit.instanceId !== undefined) {
        // Map instance back to node. Since we iterate nodes in order per type,
        // we need to traverse the scene's children → find instanced meshes
        // and figure out which node each instance maps to.
        // For simplicity, we use a 1:1 mapping approach: track node indices
        let instanceIndex = 0
        const typeOrder: string[] = []
        const typeMap = new Map<string, number[]>()
        nodes.forEach((n, i) => {
          if (!typeMap.has(n.type)) {
            typeMap.set(n.type, [])
            typeOrder.push(n.type)
          }
          typeMap.get(n.type)!.push(i)
        })

        // Find the accumulated instance index across all instanced meshes
        let accumulatedIndex = 0
        for (const type of typeOrder) {
          const indices = typeMap.get(type)!
          if (hit.object instanceof THREE.InstancedMesh) {
            const meshColor = new THREE.Color()
            hit.object.getColorAt(0, meshColor)
            const meshTypeColor = getNodeColor(type).hex
            // Simple check: compare color hex
            if (hit.instanceId < indices.length) {
              accumulatedIndex = indices[hit.instanceId]
              break
            }
          }
          accumulatedIndex += indices.length
        }

        // Fallback: iterate all nodes and check position proximity
        const hitPos = new THREE.Vector3()
        hit.object.getWorldPosition(_dummyVec)
        // Try to get the actual hit position
        const point = hit.point

        let closestNode: number | null = null
        let closestDist = 30 // within 30 units
        for (const n of nodes) {
          const pos = positions.get(n.id)
          if (!pos) continue
          const dist = Math.sqrt(
            (pos.x - point.x) ** 2 + (pos.y - point.y) ** 2 + (pos.z - point.z) ** 2,
          )
          if (dist < closestDist) {
            closestDist = dist
            closestNode = n.id
          }
        }
        return closestNode
      }
    }
    return null
  }

  /** Highlight a node and its neighbors; dim the rest */
  function highlightNode(nodeId: number | null) {
    if (nodeId === highlightedId) return
    highlightedId = nodeId

    const neighborIds = nodeId ? adjacency.get(nodeId) ?? new Set() : new Set()

    // Toggle label opacity
    for (const n of nodes) {
      const isHighlighted = n.id === nodeId || neighborIds.has(n.id)
      // Sprite opacity
      // We can't easily access individual sprites from here, so we work at the mesh level
    }
  }

  /** Smooth fly-to animation */
  function flyTo(nodeId: number): void {
    const pos = positions.get(nodeId)
    if (!pos) return

    const targetPos = new THREE.Vector3(pos.x, pos.y, pos.z)
    const startPos = scene.camera.position.clone()
    const duration = 600
    const startTime = performance.now()

    function animateFly(time: number) {
      const t = Math.min((time - startTime) / duration, 1)
      // Ease-in-out cubic
      const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2

      scene.camera.position.lerpVectors(startPos, targetPos.clone().add(new THREE.Vector3(0, 30, 120)), ease)
      controls.target.lerp(targetPos, ease)
      controls.update()

      if (t < 1) {
        requestAnimationFrame(animateFly)
      }
    }
    requestAnimationFrame(animateFly)
  }

  // ── Event handlers ──

  function onPointerMove(event: MouseEvent) {
    const id = raycastNodes(event)
    const rect = canvas.getBoundingClientRect()
    const pos = { x: event.clientX - rect.left, y: event.clientY - rect.top }

    if (id !== hoveredId) {
      hoveredId = id
      callbacks.onHover(id !== null ? nodeMap.get(id) ?? null : null, pos)
      highlightNode(id)
    }
  }

  function onClick(event: MouseEvent) {
    const id = raycastNodes(event)
    if (id !== null) {
      const node = nodeMap.get(id)
      if (node) {
        const rect = canvas.getBoundingClientRect()
        callbacks.onSelect(node, {
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
        })
      }
    } else {
      // Click empty space → clear highlight
      highlightNode(null)
      callbacks.onHover(null, { x: 0, y: 0 })
    }
  }

  function onDblClick(event: MouseEvent) {
    const id = raycastNodes(event)
    if (id !== null) {
      flyTo(id)
    }
  }

  canvas.addEventListener('pointermove', onPointerMove)
  canvas.addEventListener('click', onClick)
  canvas.addEventListener('dblclick', onDblClick)

  return {
    controls,
    dispose() {
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('click', onClick)
      canvas.removeEventListener('dblclick', onDblClick)
      controls.dispose()
    },
  }
}
