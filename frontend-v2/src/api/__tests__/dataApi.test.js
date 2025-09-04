/**
 * @vitest-environment jsdom
 */
import { dataApi } from '../dataApi'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
})

test('exportDatabase requests /data/export', async () => {
  const mockData = { foo: 'bar' }
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockData),
    })
  )

  const result = await dataApi.exportDatabase()

  const [url, opts] = global.fetch.mock.calls[0]
  expect(url).toContain('/data/export')
  expect(opts).toEqual({
    headers: { 'Content-Type': 'application/json' },
  })
  expect(result).toEqual(mockData)
})

test('importDatabase posts payload with mode', async () => {
  const payload = { a: 1 }
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true }),
    })
  )

  const result = await dataApi.importDatabase(payload, 'merge')

  const [url, opts] = global.fetch.mock.calls[0]
  expect(url).toContain('/data/import?mode=merge')
  expect(opts).toEqual({
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
  })
  expect(result).toEqual({ success: true })
})

