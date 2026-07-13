import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from '../../sandbox/node_modules/typescript/lib/typescript.js'

const source = await readFile(new URL('./resourceReferences.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const resourceReferences = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
const {
  normalizeRefItem,
  normalizeRefItems,
  referenceDisplayName,
  referenceOpenTarget,
  uniqueRefs,
} = resourceReferences

test('canonical file references open from id and display_name', () => {
  const ref = normalizeRefItem({
    type: 'file',
    id: 42,
    file_id: 999,
    display_name: 'contract.docx',
    locator: '',
    mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    access_scope: 'user',
    provenance: {},
  })

  assert.ok(ref)
  assert.equal(ref.id, 42)
  assert.equal(referenceDisplayName(ref), 'contract.docx')
  assert.match(referenceOpenTarget(ref), /^app:\/\/file\/open\?file_id=42&/)
  assert.doesNotMatch(referenceOpenTarget(ref), /999/)
})

test('canonical URL references open only from locator', () => {
  const ref = normalizeRefItem({
    type: 'url',
    id: 'source-1',
    display_name: 'Official docs',
    locator: 'https://example.com/canonical',
    url: 'https://example.com/legacy',
    mime_type: 'text/html',
    access_scope: 'user',
    provenance: {},
  })

  assert.ok(ref)
  assert.equal(referenceOpenTarget(ref), 'https://example.com/canonical')
})

test('deduplication uses type, id, and locator instead of title', () => {
  const refs = normalizeRefItems([
    { type: 'record', id: 1, display_name: 'Same title', locator: 'db://records/1' },
    { type: 'record', id: 2, display_name: 'Same title', locator: 'db://records/2' },
  ])
  assert.equal(refs.length, 2)

  const duplicate = { ...refs[0], display_name: 'Renamed record' }
  assert.equal(uniqueRefs([refs[0], duplicate]).length, 1)
})

test('legacy persisted references are normalized once at the input boundary', () => {
  const [fileRef, urlRef] = normalizeRefItems([
    { type: 'file', file_id: 7, title: 'Legacy file', format: 'pdf', page: 3 },
    { type: 'web', title: 'Legacy link', url: 'https://example.com/legacy' },
  ])

  assert.equal(fileRef.id, 7)
  assert.equal(fileRef.display_name, 'Legacy file')
  assert.match(referenceOpenTarget(fileRef), /file_id=7/)
  assert.equal(urlRef.type, 'url')
  assert.equal(referenceOpenTarget(urlRef), 'https://example.com/legacy')
})
