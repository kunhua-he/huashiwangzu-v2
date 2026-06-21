/**
 * Self-developed 3D force-directed layout engine.
 *
 * Pure TS, no Three.js dependency. Produces {x,y,z} positions.
 * - Coulomb repulsion (O(n²) for ≤300 nodes, grid-bucketed for larger sets)
 * - Spring attraction along edges (weighted)
 * - Centripetal pull toward origin
 * - Converges when energy drops below threshold
 * - Supports incremental addition (new nodes without full recompute)
 */

import type { GraphEdge, GraphNode } from './types'

/** 3D position */
export interface LayoutPosition {
  x: number
  y: number
  z: number
}

/** Internal layout node */
interface LayoutNode {
  id: number
  label: string
  type: string
  weight?: number
  x: number
  y: number
  z: number
  vx: number
  vy: number
  vz: number
}

/** Layout configuration */
export interface LayoutOptions {
  /** Coulomb repulsion strength (default: 800) */
  repulsion?: number
  /** Spring stiffness (default: 0.006) */
  springStiffness?: number
  /** Spring rest length (default: 60) */
  restLength?: number
  /** Centripetal pull (default: 0.002) */
  centripetal?: number
  /** Velocity damping per iteration (default: 0.65) */
  damping?: number
  /** Energy threshold for convergence (default: 0.5) */
  energyThreshold?: number
  /** Max iterations (default: 150) */
  maxIterations?: number
  /** Spatial bounds radius (default: 400) */
  bounds?: number
}

const defaults: Required<LayoutOptions> = {
  repulsion: 1200,
  springStiffness: 0.005,
  restLength: 80,
  centripetal: 0.0015,
  damping: 0.65,
  energyThreshold: 0.5,
  maxIterations: 200,
  bounds: 500,
}

/** Run force-directed layout, returning positions keyed by node id */
export function computeLayout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  options: LayoutOptions = {},
): Map<number, LayoutPosition> {
  const opts = { ...defaults, ...options }
  const count = nodes.length
  if (count === 0) return new Map()

  const bound = opts.bounds
  const lays: LayoutNode[] = nodes.map((n, i) => {
    // Distribute initial positions on a sphere
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    const r = bound * 0.25 + Math.random() * bound * 0.2
    return {
      id: n.id,
      label: n.label,
      type: n.type,
      weight: n.weight,
      x: Math.cos(theta) * Math.sin(phi) * r,
      y: Math.sin(theta) * Math.sin(phi) * r,
      z: Math.cos(phi) * r,
      vx: 0, vy: 0, vz: 0,
    }
  })

  const idIndex = new Map<number, number>()
  lays.forEach((n, i) => idIndex.set(n.id, i))

  // Build adjacency list for spring forces
  const adjacency: Array<{ target: number; weight: number }[]> = lays.map(() => [])
  for (const e of edges) {
    const si = idIndex.get(e.source)
    const ti = idIndex.get(e.target)
    if (si === undefined || ti === undefined) continue
    if (si === ti) continue
    // Avoid duplicates
    if (!adjacency[si].some(a => a.target === ti)) {
      adjacency[si].push({ target: ti, weight: e.weight })
    }
    if (!adjacency[ti].some(a => a.target === si)) {
      adjacency[ti].push({ target: si, weight: e.weight })
    }
  }

  // Grid bucketing for large-node repulsion
  const useGrid = count > 300
  const cellSize = bound * 0.4

  function getCell(x: number, y: number, z: number): string {
    const cx = Math.floor(x / cellSize)
    const cy = Math.floor(y / cellSize)
    const cz = Math.floor(z / cellSize)
    return `${cx},${cy},${cz}`
  }

  let energy = Infinity
  for (let iter = 0; iter < opts.maxIterations && energy > opts.energyThreshold; iter++) {
    // Build grid if needed
    const grid = useGrid ? new Map<string, number[]>() : null
    if (useGrid && grid) {
      lays.forEach((n, i) => {
        const cell = getCell(n.x, n.y, n.z)
        const bucket = grid.get(cell) ?? []
        bucket.push(i)
        grid.set(cell, bucket)
      })
    }

    // Reset velocities
    for (const n of lays) { n.vx = 0; n.vy = 0; n.vz = 0 }

    // Coulomb repulsion (all pairs)
    if (useGrid && grid) {
      // Grid-bucketed approximation
      for (let a = 0; a < count; a++) {
        const na = lays[a]
        const cell = getCell(na.x, na.y, na.z)
        // Check nearby cells (3x3x3)
        for (let dx = -1; dx <= 1; dx++) {
          for (let dy = -1; dy <= 1; dy++) {
            for (let dz = -1; dz <= 1; dz++) {
              const parts = cell.split(',')
              const nc = `${Number(parts[0]) + dx},${Number(parts[1]) + dy},${Number(parts[2]) + dz}`
              const bucket = grid.get(nc)
              if (!bucket) continue
              for (const b of bucket) {
                if (a >= b) continue
                const nb = lays[b]
                const dx2 = nb.x - na.x, dy2 = nb.y - na.y, dz2 = nb.z - na.z
                const dist = Math.max(1, Math.sqrt(dx2 * dx2 + dy2 * dy2 + dz2 * dz2))
                const force = opts.repulsion / (dist * dist)
                const fx = (dx2 / dist) * force
                const fy = (dy2 / dist) * force
                const fz = (dz2 / dist) * force
                na.vx -= fx; na.vy -= fy; na.vz -= fz
                nb.vx += fx; nb.vy += fy; nb.vz += fz
              }
            }
          }
        }
      }
    } else {
      // Exact O(n²)
      for (let a = 0; a < count; a++) {
        for (let b = a + 1; b < count; b++) {
          const na = lays[a], nb = lays[b]
          const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy + dz * dz))
          const force = opts.repulsion / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          const fz = (dz / dist) * force
          na.vx -= fx; na.vy -= fy; na.vz -= fz
          nb.vx += fx; nb.vy += fy; nb.vz += fz
        }
      }
    }

    // Spring attraction along edges
    for (let i = 0; i < count; i++) {
      for (const edge of adjacency[i]) {
        const na = lays[i], nb = lays[edge.target]
        const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy + dz * dz))
        const displacement = dist - opts.restLength
        const force = displacement * opts.springStiffness * edge.weight
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        const fz = (dz / dist) * force
        na.vx += fx; na.vy += fy; na.vz += fz
        nb.vx -= fx; nb.vy -= fy; nb.vz -= fz
      }
    }

    // Centripetal pull toward origin
    for (const n of lays) {
      n.vx -= n.x * opts.centripetal
      n.vy -= n.y * opts.centripetal
      n.vz -= n.z * opts.centripetal
    }

    // Category cluster: pull same-type nodes together
    if (!useGrid) {
      const catGroup = new Map<string, number[]>()
      lays.forEach((n, i) => {
        const t = n.type
        if (!catGroup.has(t)) catGroup.set(t, [])
        catGroup.get(t)!.push(i)
      })
      for (const [, indices] of catGroup) {
        if (indices.length < 2) continue
        for (let a = 0; a < indices.length; a++) {
          for (let b = a + 1; b < indices.length; b++) {
            const na = lays[indices[a]], nb = lays[indices[b]]
            const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z
            const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy + dz * dz))
            const force = dist * 0.0003  // Gentle pull proportional to distance
            na.vx += (dx / dist) * force
            na.vy += (dy / dist) * force
            na.vz += (dz / dist) * force
            nb.vx -= (dx / dist) * force
            nb.vy -= (dy / dist) * force
            nb.vz -= (dz / dist) * force
          }
        }
      }
    }

    // Apply damping and update positions
    energy = 0
    for (const n of lays) {
      if (!isFinite(n.vx)) n.vx = 0
      if (!isFinite(n.vy)) n.vy = 0
      if (!isFinite(n.vz)) n.vz = 0
      n.vx *= opts.damping
      n.vy *= opts.damping
      n.vz *= opts.damping
      n.x += n.vx; n.y += n.vy; n.z += n.vz
      // Clamp
      n.x = Math.max(-bound, Math.min(bound, n.x))
      n.y = Math.max(-bound, Math.min(bound, n.y))
      n.z = Math.max(-bound, Math.min(bound, n.z))
      energy += n.vx * n.vx + n.vy * n.vy + n.vz * n.vz
    }
    energy /= Math.max(1, count)
  }

  const result = new Map<number, LayoutPosition>()
  lays.forEach(n => result.set(n.id, { x: n.x, y: n.y, z: n.z }))
  return result
}

/**
 * Incremental layout: add new nodes without full recompute.
 * Places new nodes near their connected neighbors, then runs a short relaxation.
 */
export function incrementalLayout(
  existingPositions: Map<number, LayoutPosition>,
  newNodes: GraphNode[],
  allEdges: GraphEdge[],
  options: LayoutOptions = {},
): Map<number, LayoutPosition> {
  const opts = { ...defaults, ...options }
  const positions = new Map(existingPositions)

  // Place new nodes near their connected neighbors
  for (const n of newNodes) {
    const connectedEdges = allEdges.filter(e => e.source === n.id || e.target === n.id)
    if (connectedEdges.length > 0) {
      let avgX = 0, avgY = 0, avgZ = 0, count = 0
      for (const e of connectedEdges) {
        const neighborId = e.source === n.id ? e.target : e.source
        const pos = positions.get(neighborId)
        if (pos) { avgX += pos.x; avgY += pos.y; avgZ += pos.z; count++ }
      }
      if (count > 0) {
        const spread = opts.restLength * 0.5
        positions.set(n.id, {
          x: avgX / count + (Math.random() - 0.5) * spread,
          y: avgY / count + (Math.random() - 0.5) * spread,
          z: avgZ / count + (Math.random() - 0.5) * spread,
        })
        continue
      }
    }
    // Fallback: random position within bounds
    const bound = opts.bounds * 0.5
    positions.set(n.id, {
      x: (Math.random() - 0.5) * bound * 2,
      y: (Math.random() - 0.5) * bound * 2,
      z: (Math.random() - 0.5) * bound * 2,
    })
  }

  // Short relaxation (30 iterations)
  const allNodes: GraphNode[] = []
  const existingIds = new Set(existingPositions.keys())
  for (const id of existingIds) {
    allNodes.push({ id, label: '', type: '' })
  }
  allNodes.push(...newNodes)

  const idIndex = new Map<number, number>()
  allNodes.forEach((n, i) => idIndex.set(n.id, i))

  const lays = allNodes.map(n => {
    const p = positions.get(n.id)!
    return { id: n.id, label: n.label, type: n.type, weight: n.weight, x: p.x, y: p.y, z: p.z, vx: 0, vy: 0, vz: 0 }
  })

  const adjacency: Array<{ target: number; weight: number }[]> = lays.map(() => [])
  for (const e of allEdges) {
    const si = idIndex.get(e.source); const ti = idIndex.get(e.target)
    if (si === undefined || ti === undefined || si === ti) continue
    if (!adjacency[si].some(a => a.target === ti)) {
      adjacency[si].push({ target: ti, weight: e.weight })
      adjacency[ti].push({ target: si, weight: e.weight })
    }
  }

  for (let iter = 0; iter < 30; iter++) {
    for (const n of lays) { n.vx = 0; n.vy = 0; n.vz = 0 }

    const count2 = lays.length
    for (let a = 0; a < count2; a++) {
      for (let b = a + 1; b < count2; b++) {
        const na = lays[a], nb = lays[b]
        const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy + dz * dz))
        const force = opts.repulsion / (dist * dist)
        na.vx -= (dx / dist) * force; na.vy -= (dy / dist) * force; na.vz -= (dz / dist) * force
        nb.vx += (dx / dist) * force; nb.vy += (dy / dist) * force; nb.vz += (dz / dist) * force
      }
    }

    for (let i = 0; i < count2; i++) {
      for (const edge of adjacency[i]) {
        const na = lays[i], nb = lays[edge.target]
        const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy + dz * dz))
        const disp = dist - opts.restLength
        const force = disp * opts.springStiffness * edge.weight
        na.vx += (dx / dist) * force; na.vy += (dy / dist) * force; na.vz += (dz / dist) * force
        nb.vx -= (dx / dist) * force; nb.vy -= (dy / dist) * force; nb.vz -= (dz / dist) * force
      }
    }

    for (const n of lays) {
      n.vx -= n.x * opts.centripetal; n.vy -= n.y * opts.centripetal; n.vz -= n.z * opts.centripetal
      if (!isFinite(n.vx)) n.vx = 0; if (!isFinite(n.vy)) n.vy = 0; if (!isFinite(n.vz)) n.vz = 0
      n.vx *= opts.damping; n.vy *= opts.damping; n.vz *= opts.damping
      n.x += n.vx; n.y += n.vy; n.z += n.vz
      positions.set(n.id, { x: n.x, y: n.y, z: n.z })
    }
  }

  return positions
}
