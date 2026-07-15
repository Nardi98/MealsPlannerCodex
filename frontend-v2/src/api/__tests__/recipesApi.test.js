/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { recipesApi } from '../recipesApi'

afterEach(() => {
  vi.restoreAllMocks()
})

test('uploadImage posts the file as multipart and returns the image_url', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ image_url: 'http://api/recipes/images/recipes/a.png' }),
    })
  )

  const file = new File(['bytes'], 'a.png', { type: 'image/png' })
  const url = await recipesApi.uploadImage(file)

  expect(url).toBe('http://api/recipes/images/recipes/a.png')
  const [path, opts] = globalThis.fetch.mock.calls[0]
  expect(path).toContain('/recipes/upload-image')
  expect(opts.method).toBe('POST')
  expect(opts.body).toBeInstanceOf(FormData)
  expect(opts.body.get('file')).toBe(file)
})
