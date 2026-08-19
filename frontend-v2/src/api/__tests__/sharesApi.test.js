/**
 * @vitest-environment jsdom
 */
import { sharesApi } from '../sharesApi'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockJson(data, status = 200) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status, json: () => Promise.resolve(data) })
  )
}

function mockError(status, detail) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: false,
      status,
      text: () => Promise.resolve(JSON.stringify({ detail })),
    })
  )
}

test('create posts mode/recipient/expiry to /recipes/{id}/shares', async () => {
  mockJson({ id: 5, mode: 'link', url: 'https://x/shared/tok', active: true }, 201)

  const share = await sharesApi.create(7, {
    mode: 'link',
    recipient_email: 'a@b.c',
    expires_at: '2026-09-01T00:00:00Z',
  })

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/recipes/7/shares')
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({
    mode: 'link',
    recipient_email: 'a@b.c',
    expires_at: '2026-09-01T00:00:00Z',
  })
  expect(share.url).toBe('https://x/shared/tok')
})

// SH-5: link mode has an optional recipient; blanks must go over as null rather
// than as an empty string the API would try to validate as an address.
test('create sends nulls for an omitted recipient and expiry', async () => {
  mockJson({ id: 6, mode: 'link', url: 'https://x/shared/t2' }, 201)

  await sharesApi.create(3, { mode: 'link', recipient_email: '', expires_at: '' })

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(JSON.parse(opts.body)).toEqual({
    mode: 'link',
    recipient_email: null,
    expires_at: null,
  })
})

test('create defaults to link mode', async () => {
  mockJson({ id: 9, mode: 'link', url: 'https://x/shared/t3' }, 201)

  await sharesApi.create(3, {})

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(JSON.parse(opts.body).mode).toBe('link')
})

// SH-9: a date-only value from <input type="date"> must reach the API as a full
// ISO-8601 datetime, which is what the backend schema parses.
test('create widens a date-only expiry to an ISO datetime', async () => {
  mockJson({ id: 10, mode: 'link', url: 'https://x/shared/t4' }, 201)

  await sharesApi.create(3, { expires_at: '2026-09-01' })

  const [, opts] = globalThis.fetch.mock.calls[0]
  const sent = JSON.parse(opts.body).expires_at
  expect(sent).toBe(new Date('2026-09-01T23:59:59').toISOString())
})

test('list fetches the recipe shares', async () => {
  mockJson([{ id: 1, mode: 'link', active: true }])

  const shares = await sharesApi.list(7)

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/recipes/7/shares')
  expect(opts.method ?? 'GET').toBe('GET')
  expect(shares).toHaveLength(1)
})

test('revoke deletes the share and resolves on 204', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 204 }))

  const result = await sharesApi.revoke(12)

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/shares/12')
  expect(opts.method).toBe('DELETE')
  expect(result).toBeNull()
})

// SH-11: the rate limiter is a normal, recoverable situation — the caller needs
// to distinguish it from a generic failure to word the message calmly.
test('create surfaces a rate-limit 429 with a recognisable error', async () => {
  mockError(429, 'Too many shares created')

  await expect(sharesApi.create(1, {})).rejects.toMatchObject({ status: 429 })
})
