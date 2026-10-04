/**
 * @vitest-environment jsdom
 */
import { beforeEach, expect, test, vi } from 'vitest'

// The admin feedback routes are a frozen contract the backend router is
// written against independently, so path, verb and serialised body are pinned.
vi.mock('../client', () => ({
  request: vi.fn(() => Promise.resolve(null)),
  requestBlob: vi.fn(() => Promise.resolve(null)),
}))

const { request, requestBlob } = await import('../client')
const { userFeedbackAdminApi, default: asDefault } = await import('../userFeedbackAdminApi')

beforeEach(() => {
  request.mockClear()
  requestBlob.mockClear()
})

test('is exported both named and as the default', () => {
  expect(asDefault).toBe(userFeedbackAdminApi)
})

test('list with no filters GETs the bare collection', async () => {
  await userFeedbackAdminApi.list()
  await userFeedbackAdminApi.list({})

  expect(request.mock.calls).toEqual([['/admin/feedback'], ['/admin/feedback']])
})

test('list puts only the filters that are set in the query string', async () => {
  await userFeedbackAdminApi.list({ status: 'open', type: '', priority: null, tag: 'mobile ui', seen: false })

  expect(request.mock.calls[0]).toEqual(['/admin/feedback?status=open&tag=mobile+ui&seen=false'])
})

test('unseenCount GETs the badge count', async () => {
  await userFeedbackAdminApi.unseenCount()

  expect(request.mock.calls[0]).toEqual(['/admin/feedback/unseen-count'])
})

test('get GETs one item', async () => {
  await userFeedbackAdminApi.get(7)

  expect(request.mock.calls[0]).toEqual(['/admin/feedback/7'])
})

test('update PATCHes exactly the patch it is given', async () => {
  await userFeedbackAdminApi.update(7, { seen: true })

  expect(request.mock.calls[0]).toEqual([
    '/admin/feedback/7',
    { method: 'PATCH', body: '{"seen":true}' },
  ])
})

test('listTags GETs the feedback vocabulary', async () => {
  await userFeedbackAdminApi.listTags()

  expect(request.mock.calls[0]).toEqual(['/admin/feedback/tags'])
})

test('renameTag PATCHes the tag with its new name', async () => {
  await userFeedbackAdminApi.renameTag(3, 'mobile')

  expect(request.mock.calls[0]).toEqual([
    '/admin/feedback/tags/3',
    { method: 'PATCH', body: '{"name":"mobile"}' },
  ])
})

test('screenshot fetches the bytes through requestBlob, not request', async () => {
  await userFeedbackAdminApi.screenshot(7)

  expect(requestBlob.mock.calls[0]).toEqual(['/admin/feedback/7/screenshot'])
  expect(request).not.toHaveBeenCalled()
})
