/**
 * Three.js scene setup: camera, lights, renderer, bloom, starfield background, grid floor.
 *
 * Pure TS — no Vue dependency. Creates and owns a THREE.Scene.
 */

/// <reference path="./three.d.ts" />

import { THREE, EffectComposer, RenderPass, UnrealBloomPass } from './three-addons'

import { theme, type ThemePalette } from './theme'
import type { GraphEngineOptions } from './types'

/** Scene context returned by createScene() */
export interface SceneContext {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer
  composer: EffectComposer
  bloomPass: UnrealBloomPass
  starField: THREE.Points
  dispose: () => void
}

/**
 * Create the full Three.js scene: canvas, camera, lights, bloom, stars, grid.
 */
export function createScene(
  canvas: HTMLCanvasElement,
  options: GraphEngineOptions = {},
): SceneContext {
  const pal = theme

  // ── Renderer ──
  const dpr = Math.min(window.devicePixelRatio || 1, options.maxPixelRatio ?? 2)
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(dpr)
  renderer.setClearColor(options.backgroundColor ?? pal.bg.void, 1)
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0

  // ── Scene ──
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(options.backgroundColor ?? pal.bg.void)

  // ── Camera ──
  const aspect = canvas.clientWidth / Math.max(1, canvas.clientHeight)
  const camera = new THREE.PerspectiveCamera(45, aspect, 1, 3000)
  camera.position.set(0, 200, 500)
  camera.lookAt(0, 0, 0)

  // ── Ambient light ──
  const ambient = new THREE.AmbientLight(0x446688, 0.4)
  scene.add(ambient)

  // ── Directional light (subtle, to give spheres depth) ──
  const dir = new THREE.DirectionalLight(0xffffff, 0.6)
  dir.position.set(200, 400, 300)
  scene.add(dir)
  const dirFill = new THREE.DirectionalLight(0x6688cc, 0.3)
  dirFill.position.set(-200, -100, -150)
  scene.add(dirFill)

  // ── Star field background ──
  const starCount = 2000
  const starGeo = new THREE.BufferGeometry()
  const starPos = new Float32Array(starCount * 3)
  for (let i = 0; i < starCount * 3; i++) {
    starPos[i] = (Math.random() - 0.5) * 2000
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3))
  const starMat = new THREE.PointsMaterial({
    color: 0xc0d8ff,
    size: 0.8,
    transparent: true,
    opacity: 0.6,
    sizeAttenuation: true,
  })
  const starField = new THREE.Points(starGeo, starMat)
  starField.position.set(0, 0, 0)
  scene.add(starField)

  // ── Grid floor (faint coordinate grid for depth perception) ──
  const gridHelper = new THREE.GridHelper(600, 40, 0x2a5680, 0x1a3a60)
  gridHelper.position.y = -200
  gridHelper.material.transparent = true
  gridHelper.material.opacity = 0.15
  scene.add(gridHelper)

  // ── Composer + Bloom ──
  const composer = new EffectComposer(renderer)
  const renderPass = new RenderPass(scene, camera)
  composer.addPass(renderPass)

  const bloomStrength = options.bloomStrength ?? 0.6
  const bloomRadius = options.bloomRadius ?? 0.4
  const bloomThreshold = options.bloomThreshold ?? 0.1
  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(canvas.clientWidth, canvas.clientHeight),
    bloomStrength,
    bloomRadius,
    bloomThreshold,
  )
  if (!(options.bloomEnabled ?? true)) {
    bloomPass.enabled = false
  }
  composer.addPass(bloomPass)

  return {
    scene,
    camera,
    renderer,
    composer,
    bloomPass,
    starField,
    dispose() {
      renderer.dispose()
      composer.dispose()
      scene.clear()
    },
  }
}

/** Resize handler — call on container resize or fullscreen toggle */
export function resizeScene(ctx: SceneContext): void {
  const canvas = ctx.renderer.domElement
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (w === 0 || h === 0) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  ctx.renderer.setSize(w, h, false)
  ctx.camera.aspect = w / h
  ctx.camera.updateProjectionMatrix()
  ctx.composer.setSize(w * dpr, h * dpr)
}
