/**
 * @vitest-environment jsdom
 */
// ALPHA-GATE: tests for the closed-alpha allowlist client. Deleted whole with
// the alpha (docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md).
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

// The four admin routes are a frozen contract the backend router is written
// against independently, so the path, the verb and the *serialised* body are
// what these tests pin -- notably the POST field name `emails`.
vi.mock('../client', () => ({ request: vi.fn(() => Promise.resolve(null)) }))

const { request } = await import('../client')
const { alphaApi } = await import('../alphaApi')
// Vite's `?raw` gives the module text; `node:fs` cannot, since jsdom rewrites
// `import.meta.url` to an http URL.
const source = (await import('../alphaApi.js?raw')).default

const callOf = (call = 0) => request.mock.calls[call]

beforeEach(() => {
  request.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('list GETs the invites collection with no options', async () => {
  await alphaApi.list()

  expect(callOf()).toEqual(['/admin/alpha/invites'])
})

test('add POSTs the raw text under the field name emails', async () => {
  await alphaApi.add('a@x.com, b@x.com')

  expect(callOf()).toEqual([
    '/admin/alpha/invites',
    { method: 'POST', body: '{"emails":"a@x.com, b@x.com"}' },
  ])
})

test('updateNote PATCHes the note onto the invite', async () => {
  await alphaApi.updateNote(7, 'note')

  expect(callOf()).toEqual([
    '/admin/alpha/invites/7',
    { method: 'PATCH', body: '{"note":"note"}' },
  ])
})

test('updateNote sends an explicit null so a note can be cleared', async () => {
  await alphaApi.updateNote(7, null)

  expect(callOf()[1].body).toBe('{"note":null}')
})

test('remove DELETEs the invite', async () => {
  await alphaApi.remove(7)

  expect(callOf()).toEqual(['/admin/alpha/invites/7', { method: 'DELETE' }])
})

test('an id needing escaping is encoded into the path', async () => {
  await alphaApi.remove('7 8/9')

  expect(callOf()[0]).toBe('/admin/alpha/invites/7%208%2F9')
})

test('the module defines no error-text helper of its own', () => {
  // `apiErrorText` / `asSentence` live in `catalogApi` and are imported from
  // there by the page; a second copy here would drift.
  expect(source).not.toMatch(/apiErrorText|asSentence/)
})

test('the module is marked for removal with the alpha', () => {
  expect(source.split('\n').slice(0, 20).join('\n')).toContain('ALPHA-GATE')
})
