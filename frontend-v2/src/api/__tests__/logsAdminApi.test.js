/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { logsAdminApi } from '../logsAdminApi'

afterEach(() => {
  vi.restoreAllMocks()
})

const respondWith = (body) => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
  )
}

test('searchUsers queries by email or username', async () => {
  respondWith([{ id: 1, email: 'a@x.com', username: 'a' }])

  const users = await logsAdminApi.searchUsers('a@x')

  expect(globalThis.fetch.mock.calls[0][0]).toContain('/admin/logs/users?q=a%40x')
  expect(users).toEqual([{ id: 1, email: 'a@x.com', username: 'a' }])
})

test('exportLog asks for one user, optionally one channel', async () => {
  respondWith({ user: { id: 1 }, entries: [] })

  await logsAdminApi.exportLog(1, 'planner')
  await logsAdminApi.exportLog(1)

  expect(globalThis.fetch.mock.calls[0][0]).toContain('/admin/logs/export?user_id=1&channel=planner')
  expect(globalThis.fetch.mock.calls[1][0]).toMatch(/\/admin\/logs\/export\?user_id=1$/)
})
