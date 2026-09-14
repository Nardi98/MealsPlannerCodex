/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { downloadJson } from '../download'

let written
let clicks

beforeEach(() => {
  written = []
  clicks = []
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  vi.stubGlobal(
    'Blob',
    class FakeBlob {
      constructor(parts, options) {
        written.push({ parts, type: options?.type })
      }
    },
  )
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function record() {
    clicks.push({ href: this.getAttribute('href'), download: this.download, attached: document.body.contains(this) })
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

test('saves the data as pretty-printed JSON under the filename', () => {
  downloadJson({ a: 1 }, 'backup.json')

  expect(written).toEqual([{ parts: [JSON.stringify({ a: 1 }, null, 2)], type: 'application/json' }])
  expect(clicks).toEqual([{ href: 'blob:x', download: 'backup.json', attached: true }])
})

test('removes the link and revokes the URL afterwards', () => {
  downloadJson([], 'x.json')

  expect(document.querySelector('a[download]')).toBeNull()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x')
})

test('cleans up even when the click throws', () => {
  HTMLAnchorElement.prototype.click.mockImplementation(() => {
    throw new Error('blocked')
  })

  expect(() => downloadJson([], 'x.json')).toThrow('blocked')
  expect(document.querySelector('a[download]')).toBeNull()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x')
})
