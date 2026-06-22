/**
 * Three.js addons re-export shim.
 *
 * Rolldown (Vite 8's default bundler) does not support Node.js wildcard subpath
 * exports (`package.json` `./examples/jsm/*` or `./addons/*` patterns).
 * This barrel re-exports the needed addon files via direct relative paths,
 * which Vite can resolve without going through the package.json exports field.
 */

export { OrbitControls } from '../../../../frontend/node_modules/three/examples/jsm/controls/OrbitControls.js'
export { EffectComposer } from '../../../../frontend/node_modules/three/examples/jsm/postprocessing/EffectComposer.js'
export { RenderPass } from '../../../../frontend/node_modules/three/examples/jsm/postprocessing/RenderPass.js'
export { UnrealBloomPass } from '../../../../frontend/node_modules/three/examples/jsm/postprocessing/UnrealBloomPass.js'
export { CSS2DRenderer, CSS2DObject } from '../../../../frontend/node_modules/three/examples/jsm/renderers/CSS2DRenderer.js'

// Re-export the THREE namespace via direct file path (bypasses export map)
export * as THREE from '../../../../frontend/node_modules/three/build/three.module.js'
