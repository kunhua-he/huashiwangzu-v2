/**
 * Minimal ambient type stubs for three.js.
 *
 * The framework tsconfig's `*: ["./node_modules/*"]` path mapping prevents
 * normal @types/three resolution from the @modules/ path. Vite still bundles
 * the actual JS correctly. These stubs give TypeScript just enough to type-check.
 */

declare module 'three' {
  export class Vector2 { constructor(x?: number, y?: number); x: number; y: number }
  export class Vector3 {
    constructor(x?: number, y?: number, z?: number)
    x: number; y: number; z: number
    lerp(v: Vector3, alpha: number): this
    lerpVectors(v1: Vector3, v2: Vector3, t: number): this
    clone(): Vector3
    add(v: Vector3): this
    set(x: number, y: number, z: number): this
    dot(v: Vector3): number
  }
  export class Color {
    constructor(color?: string | number)
    setHex(hex: number): this
  }
  export class Object3D {
    position: Vector3
    scale: Vector3
    children: Object3D[]
    add(child: Object3D): void
    remove(child: Object3D): void
    updateMatrix(): void
    matrix: unknown
    userData: Record<string, unknown>
    lookAt(v: Vector3): void
    getWorldPosition(target: Vector3): Vector3
  }
  export class Scene extends Object3D {
    background: Color | null
    clear(): void
  }
  export class PerspectiveCamera extends Object3D {
    constructor(fov?: number, aspect?: number, near?: number, far?: number)
    aspect: number
    lookAt(x: number, y: number, z: number): void
    updateProjectionMatrix(): void
  }
  export class WebGLRenderer {
    constructor(params?: { canvas?: HTMLCanvasElement; antialias?: boolean; alpha?: boolean; powerPreference?: string })
    domElement: HTMLCanvasElement
    setPixelRatio(ratio: number): void
    setClearColor(color: string, alpha: number): void
    setSize(width: number, height: number, updateStyle?: boolean): void
    toneMapping: number
    toneMappingExposure: number
    dispose(): void
  }
  export class MeshStandardMaterial {
    constructor(params?: { color?: string | number; emissive?: string | number; emissiveIntensity?: number; metalness?: number; roughness?: number; transparent?: boolean; opacity?: number; map?: CanvasTexture })
    color: Color
    opacity: number
    transparent: boolean
    map: CanvasTexture | null
    dispose(): void
  }
  export class MeshBasicMaterial {
    constructor(params?: { color?: string | number; map?: CanvasTexture; transparent?: boolean; depthWrite?: boolean; side?: number })
    map: CanvasTexture | null
    opacity: number
    transparent: boolean
    dispose(): void
  }
  export class SphereGeometry {
    constructor(radius?: number, widthSegments?: number, heightSegments?: number)
    dispose(): void
  }
  export class PlaneGeometry extends BufferGeometry {
    constructor(width?: number, height?: number, widthSegments?: number, heightSegments?: number)
  }
  export class Mesh extends Object3D {
    constructor(geometry?: BufferGeometry, material?: Material)
    geometry: BufferGeometry
    material: Material
  }
  export class InstancedMesh extends Object3D {
    constructor(geometry: SphereGeometry, material: MeshStandardMaterial, count: number)
    instanceMatrix: { needsUpdate: boolean }
    instanceColor: { needsUpdate: boolean } | null
    setMatrixAt(index: number, matrix: unknown): void
    setColorAt(index: number, color: Color): void
    count: number
    geometry: unknown
    material: unknown
    getColorAt(index: number, color: Color): void
    castShadow: boolean
    receiveShadow: boolean
  }
  export class LineSegments extends Object3D {
    constructor(geometry?: BufferGeometry, material?: LineBasicMaterial)
    geometry: BufferGeometry
    material: LineBasicMaterial
  }
  export class LineBasicMaterial {
    constructor(params?: { color?: string; transparent?: boolean; opacity?: number; depthWrite?: boolean; linewidth?: number })
    dispose(): void
    color: Color
    opacity: number
    map: CanvasTexture | null
  }
  export class BufferGeometry {
    setAttribute(name: string, attr: BufferAttribute): this
    getAttribute(name: string): BufferAttribute | undefined
    dispose(): void
  }
  export class BufferAttribute {
    constructor(array: Float32Array, itemSize: number)
    set(data: number[], offset?: number): void
    needsUpdate: boolean
    count: number
  }
  export class Float32BufferAttribute extends BufferAttribute {
    constructor(array: number[], itemSize: number)
  }
  export class Points extends Object3D {
    constructor(geometry?: BufferGeometry, material?: PointsMaterial)
  }
  export class PointsMaterial {
    constructor(params?: { color?: number; size?: number; transparent?: boolean; opacity?: number; sizeAttenuation?: boolean })
    opacity: number
    map: CanvasTexture | null
    dispose(): void
  }
  export class Sprite extends Object3D {
    constructor(material?: SpriteMaterial)
    material: SpriteMaterial
  }
  export class SpriteMaterial {
    constructor(params?: { map?: CanvasTexture; blending?: number; depthWrite?: boolean; transparent?: boolean; opacity?: number })
    map: CanvasTexture | null
    opacity: number
    transparent: boolean
    dispose(): void
    clone(): SpriteMaterial
  }
  export class CanvasTexture {
    constructor(canvas: HTMLCanvasElement)
    needsUpdate: boolean
    dispose(): void
  }
  export class AmbientLight extends Object3D {
    constructor(color?: number, intensity?: number)
  }
  export class DirectionalLight extends Object3D {
    constructor(color?: number, intensity?: number)
    position: Vector3
  }
  export class GridHelper extends Object3D {
    constructor(size?: number, divisions?: number, colorCenterLine?: number, colorGrid?: number)
    material: { transparent: boolean; opacity: number }
  }
  export class Ray {
    origin: Vector3
    direction: Vector3
  }
  export class Raycaster {
    ray: Ray
    setFromCamera(coords: Vector2, camera: PerspectiveCamera): void
    intersectObjects(objects: Object3D[]): Intersection[]
  }
  export interface Intersection {
    point: Vector3
    object: Object3D
    instanceId?: number
    distance: number
  }
  export const AdditiveBlending: number
  export const ACESFilmicToneMapping: number
  export const DoubleSide: number
  export type Material = MeshStandardMaterial | MeshBasicMaterial | LineBasicMaterial | PointsMaterial | SpriteMaterial
}
