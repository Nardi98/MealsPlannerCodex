/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import LogsAdminPage from '../LogsAdminPage'
import { logsAdminApi } from '../../api/logsAdminApi'
import { downloadJson } from '../../utils/download'
import { stubViewport } from '../../test/stubViewport'

vi.mock('../../api/logsAdminApi', async (importOriginal) => ({
  ...(await importOriginal()),
  logsAdminApi: { searchUsers: vi.fn(), exportLog: vi.fn() },
}))
vi.mock('../../utils/download', () => ({ downloadJson: vi.fn() }))

stubViewport(false)

const USERS = [
  { id: 4, email: 'cook@example.com', username: 'cook' },
  { id: 9, email: 'cookie@example.com', username: 'cookie' },
]
const LOG = { user: USERS[0], channel: 'planner', entries: [{ id: 1, event: 'generate' }] }

beforeEach(() => {
  logsAdminApi.searchUsers.mockResolvedValue(USERS)
  logsAdminApi.exportLog.mockResolvedValue(LOG)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const search = (text) => {
  fireEvent.change(screen.getByLabelText('Email or username'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
}

test('searching lists the matching accounts', async () => {
  render(<LogsAdminPage />)

  search('cook')

  expect(await screen.findByText('cook@example.com')).toBeInTheDocument()
  expect(screen.getByText('cookie@example.com')).toBeInTheDocument()
  expect(logsAdminApi.searchUsers).toHaveBeenCalledWith('cook')
})

test('a search with no match says so', async () => {
  logsAdminApi.searchUsers.mockResolvedValue([])
  render(<LogsAdminPage />)

  search('nobody')

  expect(await screen.findByText('No account matches “nobody”.')).toBeInTheDocument()
})

test('downloading saves the chosen account’s log for the chosen channel', async () => {
  render(<LogsAdminPage />)
  search('cook')
  await screen.findByText('cook@example.com')

  fireEvent.click(screen.getByRole('radio', { name: /cook@example\.com/ }))
  fireEvent.change(screen.getByLabelText('Channel'), { target: { value: 'planner' } })
  fireEvent.click(screen.getByRole('button', { name: 'Download log' }))

  await waitFor(() => expect(downloadJson).toHaveBeenCalledWith(LOG, 'devlog-cook-planner.json'))
  expect(logsAdminApi.exportLog).toHaveBeenCalledWith(4, 'planner')
})

test('every channel is the default, and nothing downloads before an account is chosen', async () => {
  render(<LogsAdminPage />)
  search('cook')
  await screen.findByText('cook@example.com')

  expect(screen.getByRole('button', { name: 'Download log' })).toBeDisabled()

  fireEvent.click(screen.getByRole('radio', { name: /cookie@example\.com/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Download log' }))

  await waitFor(() => expect(logsAdminApi.exportLog).toHaveBeenCalledWith(9, undefined))
  expect(downloadJson).toHaveBeenCalledWith(LOG, 'devlog-cookie.json')
})

test('a failed download is reported', async () => {
  logsAdminApi.exportLog.mockRejectedValue(new Error('boom'))
  render(<LogsAdminPage />)
  search('cook')
  await screen.findByText('cook@example.com')

  fireEvent.click(screen.getByRole('radio', { name: /cook@example\.com/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Download log' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t download the log')
  expect(downloadJson).not.toHaveBeenCalled()
})
