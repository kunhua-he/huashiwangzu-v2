/**
 * Node rendering: InstancedMesh spheres with glow halos (additive-blended sprites).
 *
 * Each node has:
 * - A solid sphere core (InstancedMesh for performance)
 * - A glow sprite halo behind it
 * - Color, size, and glow intensity determined by node type + weight
 */

/// <reference path="./three.d.ts" />

import { THREE } from './three-addons'
import { getNodeColor, getNodeRadius, type ColorToken } from './theme'
import type { GraphNode } from './types'
import type { LayoutPosition } from './layout3d'

/** Pre-built node rendering context */
export interface NodeRenderContext {
  coreMesh: THREE.InstancedMesh
  glowSprites: THREE.Sprite[]
  dispose: () => void
}

/** Create a glow sprite texture using a radial gradient */
function createGlowTexture(color: ColorToken, size: number): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const cx = size / 2
  const cy = size / 2
  const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, cx)
  gradient.addColorStop(0, color.hex + 'cc')
  gradient.addColorStop(0.3, color.hex + '66')
  gradient.addColorStop(0.6, color.glow)
  gradient.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  const tex = new THREE.CanvasTexture(canvas)
  tex.needsUpdate = true
  return tex
}

/** Build all node visuals from layout data */
export function buildNodes(
  nodes: GraphNode[],
  positions: Map<number, LayoutPosition>,
  scene: THREE.Scene,
): NodeRenderContext {
  if (nodes.length === 0) {
    return {
      coreMesh: new THREE.InstancedMesh(new THREE.SphereGeometry(1, 8, 8), new THREE.MeshStandardMaterial(), 0),
      glowSprites: [],
      dispose() {},
    }
  }

  // Determine max radius for glow texture size
  const maxRadius = Math.max(...nodes.map(n => getNodeRadius(n.type, n.weight)))
  const glowTextureSize = Math.max(64, Math.ceil(maxRadius * 6))

  // ── Core spheres (InstancedMesh) ──
  // Pre-compute per-instance colors and transforms
  const geometries: { geo: THREE.SphereGeometry; indices: number[]; color: string }[] = []
  const nodeByType = new Map<string, number[]>()
  nodes.forEach((n, i) => {
    const type = n.type
    if (!nodeByType.has(type)) nodeByType.set(type, [])
    nodeByType.get(type)!.push(i)
  })

  // Group by type → one InstancedMesh per type (same color, different sizes)
  const meshes: THREE.InstancedMesh[] = []
  const sprites: THREE.Sprite[] = []

  for (const [type, indices] of nodeByType) {
    const count = indices.length
    const token = getNodeColor(type)

    // Core mesh: sphere with slightly faceted look
    const geo = new THREE.SphereGeometry(1, 16, 14)
    const mat = new THREE.MeshStandardMaterial({
      color: token.hex,
      emissive: token.hex,
      emissiveIntensity: 0.3,
      metalness: 0.2,
      roughness: 0.6,
    })
    const mesh = new THREE.InstancedMesh(geo, mat, count)
    mesh.castShadow = false
    mesh.receiveShadow = false

    const dummy = new THREE.Object3D()
    const colorObj = new THREE.Color(token.hex)

    indices.forEach((nodeIndex, instanceIndex) => {
      const node = nodes[nodeIndex]
      const pos = positions.get(node.id)
      if (!pos) return

      const radius = getNodeRadius(node.type, node.weight)
      dummy.position.set(pos.x, pos.y, pos.z)
      dummy.scale.set(radius, radius, radius)
      dummy.updateMatrix()
      mesh.setMatrixAt(instanceIndex, dummy.matrix)
      mesh.setColorAt(instanceIndex, colorObj)
    })

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    meshes.push(mesh)
    scene.add(mesh)

    // ── Glow sprites ──
    const glowTex = createGlowTexture(token, glowTextureSize)
    const spriteMat = new THREE.SpriteMaterial({
      map: glowTex,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      transparent: true,
      opacity: 0.7,
    })

    indices.forEach((nodeIndex) => {
      const node = nodes[nodeIndex]
      const pos = positions.get(node.id)
      if (!pos) return

      const radius = getNodeRadius(node.type, node.weight)
      const sprite = new THREE.Sprite(spriteMat.clone())
      sprite.position.set(pos.x, pos.y, pos.z)
      sprite.scale.set(radius * 5, radius * 5, 1)
      sprites.push(sprite)
      scene.add(sprite)
    })
  }

  return {
    coreMesh: meshes[0]!, // main mesh reference for external queries
    glowSprites: sprites,
    dispose() {
      for (const m of meshes) {
        scene.remove(m)
        m.geometry.dispose()
        if (Array.isArray(m.material)) m.material.forEach((mt: THREE.Material) => mt.dispose())
        else m.material.dispose()
      }
      for (const s of sprites) {
        scene.remove(s)
        s.material.map?.dispose()
        s.material.dispose()
      }
    },
  }
}
