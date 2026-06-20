/**
 * Three.js addons re-export shim.
 *
 * Rolldown (Vite 8's default bundler) does not support Node.js wildcard subpath
 * exports (`package.json` `./examples/jsm/*` or `./addons/*` patterns).
 * This barrel re-exports the needed addon files via direct relative paths,
 * which Vite can resolve without going through the package.json exports field.
 */

// @ts-expect-error Three.js addon JS files have no TS declarations
export { OrbitControls } from '../../../../frontend/node_modules/three/examples/jsm/controls/OrbitControls.js'
// @ts-expect-error
export { EffectComposer } from '../../../../frontend/node_modules/three/examples/jsm/postprocessing/EffectComposer.js'
// @ts-expect-error
export { RenderPass } from '../../../../frontend/node_modules/three/examples/jsm/postprocessing/RenderPass.js'
// @ts-expect-error
export { UnrealBloomPass } from '../../../../frontend/node_modules/three/examples/jsm/postprocessing/UnrealBloomPass.js'
// @ts-expect-error
export { CSS2DRenderer, CSS2DObject } from '../../../../frontend/node_modules/three/examples/jsm/renderers/CSS2DRenderer.js'

// Re-export the THREE namespace via direct file path (bypasses export map)
// @ts-expect-error
export * as THREE from '../../../../frontend/node_modules/three/build/three.module.js'
