#!/usr/bin/env node
// scan-products.js
//
// Scans products/*/product.json and generates:
// 1) product-key-map.generated.ts  — catalog metadata
// 2) product-component-key-map.generated.ts — Vue entry loaders for products/*
//
// Gate4: duplicate product/app/component keys, missing required fields, and
// invalid UI contracts fail the build.

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..', '..')
const PRODUCTS_DIR = path.join(ROOT, 'products')
const OUT_DIR = path.join(ROOT, 'frontend', 'src', 'product-runtime')
const CATALOG_OUTPUT = path.join(OUT_DIR, 'product-key-map.generated.ts')
const COMPONENT_OUTPUT = path.join(OUT_DIR, 'product-component-key-map.generated.ts')

const REQUIRED_FIELDS = [
  'schemaVersion', 'productId', 'version', 'displayName',
  'entryComponentKey', 'workspaceKind',
]

const VALID_LAYOUTS = new Set([
  'finder', 'document', 'chat', 'settings', 'dashboard', 'utility',
])
const VALID_SLOT_MODES = new Set(['required', 'optional', 'none'])
const VALID_DENSITIES = new Set(['comfortable', 'compact'])

function isRecord(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function validateUiContract(name, manifest) {
  const uc = manifest.uiContract
  if (!isRecord(uc)) {
    errors.push(`${name}: missing uiContract (require kit=mac-app-v1 + layout)`)
    return null
  }
  if (uc.kit !== 'mac-app-v1') {
    errors.push(`${name}: uiContract.kit must be "mac-app-v1" (got ${JSON.stringify(uc.kit)})`)
  }
  if (!VALID_LAYOUTS.has(String(uc.layout || ''))) {
    errors.push(`${name}: uiContract.layout invalid (got ${JSON.stringify(uc.layout)})`)
  }
  if (uc.feedback && uc.feedback !== 'desktop-kit') {
    errors.push(`${name}: uiContract.feedback must be "desktop-kit" when set`)
  }
  if (uc.density && !VALID_DENSITIES.has(String(uc.density))) {
    errors.push(`${name}: uiContract.density invalid (got ${JSON.stringify(uc.density)})`)
  }
  if (uc.shell !== undefined) {
    if (!isRecord(uc.shell)) {
      errors.push(`${name}: uiContract.shell must be an object when set`)
    } else {
      if (uc.shell.useAppWindowFrame !== undefined
        && typeof uc.shell.useAppWindowFrame !== 'boolean') {
        errors.push(`${name}: uiContract.shell.useAppWindowFrame must be boolean`)
      }
      for (const slot of ['sidebar', 'toolbar', 'statusbar']) {
        if (uc.shell[slot] !== undefined && !VALID_SLOT_MODES.has(String(uc.shell[slot]))) {
          errors.push(`${name}: uiContract.shell.${slot} invalid (got ${JSON.stringify(uc.shell[slot])})`)
        }
      }
    }
  }
  return {
    kit: uc.kit,
    layout: uc.layout,
    shell: uc.shell || null,
    feedback: uc.feedback || 'desktop-kit',
    density: uc.density || 'comfortable',
  }
}

/** @type {Array<Record<string, any>>} */
const products = []
/** @type {Array<{key: string, importPath: string}>} */
const productComponents = []
const seen = new Set()
const seenAppKeys = new Map()
const seenComponentKeys = new Map()
const errors = []

function claimKey(map, key, owner, label) {
  if (!key) return
  const previous = map.get(key)
  if (previous) {
    if (previous === owner) return
    errors.push(`duplicate ${label}: ${JSON.stringify(key)} (${previous} and ${owner})`)
    return
  }
  map.set(key, owner)
}

function resolveEntryFile(entry) {
  if (entry.startsWith('products/')) return path.join(ROOT, entry)
  if (entry.startsWith('apps/')) {
    return path.join(ROOT, 'frontend', 'src', 'platform', 'components', entry)
  }
  return path.join(ROOT, 'modules', entry.split('/')[0], 'frontend', entry.slice(entry.indexOf('/') + 1))
}

if (fs.existsSync(PRODUCTS_DIR)) {
  for (const name of fs.readdirSync(PRODUCTS_DIR)) {
    if (name.startsWith('_') || name.startsWith('.')) continue
    const dir = path.join(PRODUCTS_DIR, name)
    if (!fs.statSync(dir).isDirectory()) continue
    const manifestPath = path.join(dir, 'product.json')
    if (!fs.existsSync(manifestPath)) {
      errors.push(`missing product.json: ${name}`)
      continue
    }
    let manifest
    try {
      manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'))
    } catch (e) {
      errors.push(`invalid JSON ${manifestPath}: ${e}`)
      continue
    }
    for (const field of REQUIRED_FIELDS) {
      if (!manifest[field]) errors.push(`${name}: missing ${field}`)
    }
    const pid = String(manifest.productId || '')
    if (seen.has(pid)) errors.push(`duplicate productId: ${pid}`)
    seen.add(pid)
    claimKey(seenAppKeys, pid, name, 'app key')
    for (const legacy of Array.isArray(manifest.legacyAppKeys) ? manifest.legacyAppKeys : []) {
      const legacyKey = String(legacy || '').trim()
      if (!legacyKey) {
        errors.push(`${name}: legacyAppKeys cannot contain empty values`)
        continue
      }
      claimKey(seenAppKeys, legacyKey, name, 'app key')
    }

    const uiContract = validateUiContract(name, manifest)

    const entry = String(manifest.entryComponentKey || '')
    const local = resolveEntryFile(entry)
    if (!entry || !fs.existsSync(local)) {
      errors.push(`${pid}: entry missing on disk: ${entry || '<empty>'}`)
    } else {
      claimKey(seenComponentKeys, entry, name, 'entryComponentKey')
      if (entry.startsWith('products/')) {
        // Vite alias @products → ../products
        const relFromProducts = entry.replace(/^products\//, '')
        productComponents.push({
          key: entry,
          importPath: `@products/${relFromProducts}`,
        })
      }
    }

    products.push({
      productId: pid,
      displayName: manifest.displayName,
      entryComponentKey: entry,
      workspaceKind: manifest.workspaceKind,
      category: manifest.category || '',
      icon: (manifest.iconSet && manifest.iconSet.primary) || 'Collection',
      legacyAppKeys: manifest.legacyAppKeys || [],
      fileAssociations: manifest.fileAssociations || [],
      createDocumentTypes: manifest.createDocumentTypes || [],
      windowPolicy: manifest.windowPolicy || {},
      activationPolicy: manifest.activationPolicy || {},
      visibility: manifest.visibility || {},
      description: manifest.description || '',
      uiContract,
    })
  }
}

if (errors.length) {
  console.error('[scan-products] FAILED:')
  for (const e of errors) console.error(' -', e)
  process.exit(1)
}

products.sort((a, b) => a.productId.localeCompare(b.productId))

const catalogLines = [
  '// AUTO-GENERATED FILE — DO NOT EDIT',
  '// Source of truth: products/*/product.json',
  '// Generated by frontend/scripts/scan-products.js',
  '',
  'export interface GeneratedProductEntry {',
  '  productId: string',
  '  displayName: string',
  '  entryComponentKey: string',
  '  workspaceKind: string',
  '  category: string',
  '  icon: string',
  '  legacyAppKeys: string[]',
  '  fileAssociations: Array<Record<string, unknown>>',
  '  createDocumentTypes: Array<Record<string, unknown>>',
  '  windowPolicy: Record<string, unknown>',
  '  activationPolicy: Record<string, unknown>',
  '  visibility: Record<string, unknown>',
  '  description: string',
  '  uiContract: { kit: string; layout: string; shell?: unknown; feedback?: string; density?: string } | null',
  '}',
  '',
  'export const productCatalog: GeneratedProductEntry[] = ' + JSON.stringify(products, null, 2),
  '',
  'export const productKeyMap: Record<string, GeneratedProductEntry> = Object.fromEntries(',
  '  productCatalog.map((p) => [p.productId, p]),',
  ')',
  '',
]

const compLines = [
  '// AUTO-GENERATED FILE — DO NOT EDIT',
  '// Source of truth: products/*/product.json entryComponentKey values',
  '// Generated by frontend/scripts/scan-products.js',
  "import type { Component } from 'vue'",
  '',
  'export const productComponentKeyMap: Record<string, () => Promise<{ default: Component }>> = {',
]
for (const c of productComponents) {
  compLines.push(`  '${c.key}': () => import('${c.importPath}'),`)
}
compLines.push('}')
compLines.push('')

fs.mkdirSync(OUT_DIR, { recursive: true })
fs.writeFileSync(CATALOG_OUTPUT, catalogLines.join('\n'), 'utf-8')
fs.writeFileSync(COMPONENT_OUTPUT, compLines.join('\n'), 'utf-8')
console.log(`[scan-products] Generated ${products.length} products → ${CATALOG_OUTPUT}`)
console.log(`[scan-products] Generated ${productComponents.length} product components → ${COMPONENT_OUTPUT}`)
