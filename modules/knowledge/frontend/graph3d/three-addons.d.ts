/**
 * Type declarations for three-addons.js
 * Types for the Three.js addon classes that are loaded from direct file paths
 * to bypass Vite 8's Rolldown export map resolution issue.
 */
import * as THREE_NS from 'three'

export { THREE_NS as THREE }

export class OrbitControls {
  constructor(camera: THREE_NS.PerspectiveCamera, domElement: HTMLElement)
  enableDamping: boolean
  dampingFactor: number
  rotateSpeed: number
  zoomSpeed: number
  panSpeed: number
  minDistance: number
  maxDistance: number
  target: THREE_NS.Vector3
  update(): void
  dispose(): void
}

export class EffectComposer {
  constructor(renderer: THREE_NS.WebGLRenderer)
  addPass(pass: unknown): void
  render(): void
  setSize(width: number, height: number): void
  dispose(): void
}

export class RenderPass {
  constructor(scene: THREE_NS.Scene, camera: THREE_NS.PerspectiveCamera)
}

export class UnrealBloomPass {
  constructor(resolution: THREE_NS.Vector2, strength: number, radius: number, threshold: number)
  enabled: boolean
}

export class CSS2DRenderer {
  constructor()
  domElement: HTMLElement
  setSize(width: number, height: number): void
  render(scene: unknown, camera: unknown): void
  dispose(): void
}

export class CSS2DObject extends THREE_NS.Object3D {
  constructor(element: HTMLElement)
  element: HTMLElement
  removeFromParent(): void
}
