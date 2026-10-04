/**
 * @vitest-environment jsdom
 */
import { beforeEach, expect, test, vi } from 'vitest'

// `POST /feedback` is a multipart contract the backend is written against
// independently, so the path, the verb and the form field names are pinned.
vi.mock('../client', () => ({ request: vi.fn(() => Promise.resolve({ ref_code: 'FB-1' })) }))

const { request } = await import('../client')
const { userFeedbackApi } = await import('../userFeedbackApi')

const sent = () => {
  const [path, opts] = request.mock.calls[0]
  return { path, opts, body: opts.body }
}

beforeEach(() => {
  request.mockClear()
})

test('submit POSTs the fields as multipart to /feedback and returns the response', async () => {
  const res = await userFeedbackApi.submit({
    title: 'Broken',
    body: 'It broke',
    type: 'issue',
    page_path: '/plan',
    user_agent: 'UA',
    viewport_width: 390,
  })

  const { path, opts, body } = sent()
  expect(res).toEqual({ ref_code: 'FB-1' })
  expect(path).toBe('/feedback')
  expect(opts.method).toBe('POST')
  expect(body).toBeInstanceOf(FormData)
  expect(body.get('title')).toBe('Broken')
  expect(body.get('body')).toBe('It broke')
  expect(body.get('type')).toBe('issue')
  expect(body.get('page_path')).toBe('/plan')
  expect(body.get('user_agent')).toBe('UA')
  expect(body.get('viewport_width')).toBe('390')
})

test('submit leaves out undefined optional fields and the screenshot when no file is given', async () => {
  await userFeedbackApi.submit({ title: 't', body: 'b', type: 'request' })

  const { body } = sent()
  expect(body.has('page_path')).toBe(false)
  expect(body.has('user_agent')).toBe(false)
  expect(body.has('viewport_width')).toBe(false)
  expect(body.has('screenshot')).toBe(false)
})

test('submit attaches the file under the field name screenshot', async () => {
  const file = new File(['bytes'], 'shot.png', { type: 'image/png' })
  await userFeedbackApi.submit({ title: 't', body: 'b', type: 'issue' }, file)

  const got = sent().body.get('screenshot')
  expect(got).toBeInstanceOf(File)
  expect(got.name).toBe('shot.png')
})
