/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import FeedbackAdminPage from '../FeedbackAdminPage'
import { userFeedbackAdminApi } from '../../api/userFeedbackAdminApi'
import { FeedbackBadgeProvider, useFeedbackBadge } from '../../components/feedback/FeedbackBadgeContext'
import { stubViewport } from '../../test/stubViewport'

// Only the network calls are mocked. `importOriginal` keeps the module's own
// shape, so a renamed method here fails loudly rather than silently becoming a
// fresh `vi.fn()`.
vi.mock('../../api/userFeedbackAdminApi', async (importOriginal) => ({
  ...(await importOriginal()),
  userFeedbackAdminApi: {
    list: vi.fn(),
    unseenCount: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    listTags: vi.fn(),
    renameTag: vi.fn(),
    screenshot: vi.fn(),
  },
}))

// The badge provider fetches only in admin mode, which is where this page lives.
vi.mock('../../auth/ViewModeContext', () => ({
  useViewMode: () => ({ mode: 'admin', isAdminMode: true }),
}))

const UNREAD = {
  id: 7,
  ref_code: 'FB-7',
  title: 'Shopping list crashes',
  body: 'It crashes when I tick the last item.',
  type: 'not_working',
  status: 'open',
  priority: 'high',
  seen: false,
  page_path: '/shopping-list',
  user_agent: 'Mozilla/5.0 (iPhone)',
  viewport_width: 390,
  has_screenshot: true,
  admin_notes: null,
  tags: ['mobile', 'shopping-list'],
  author: { id: 3, email: 'anna@example.com', username: 'anna', display_name: 'Anna' },
  created_at: '2026-10-01T10:00:00',
  updated_at: '2026-10-02T11:00:00',
}

const READ = {
  id: 5,
  ref_code: 'FB-5',
  title: 'Dark mode please',
  body: 'My eyes.',
  type: 'request',
  status: 'in_progress',
  priority: 'normal',
  seen: true,
  page_path: null,
  user_agent: null,
  viewport_width: null,
  has_screenshot: false,
  admin_notes: 'Later this year',
  tags: [],
  author: null,
  created_at: '2026-09-20T10:00:00',
  updated_at: '2026-09-21T10:00:00',
}

const TAGS = [
  { id: 1, name: 'mobile' },
  { id: 2, name: 'shopping-list' },
]

const shownDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

const SCREENSHOT = new Blob(['png'], { type: 'image/png' })

beforeEach(() => {
  stubViewport(false)
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network in tests')))
  URL.createObjectURL = vi.fn(() => 'blob:screenshot-7')
  URL.revokeObjectURL = vi.fn()
  userFeedbackAdminApi.list.mockResolvedValue([UNREAD, READ])
  userFeedbackAdminApi.unseenCount.mockResolvedValue({ count: 2 })
  userFeedbackAdminApi.listTags.mockResolvedValue(TAGS)
  userFeedbackAdminApi.screenshot.mockResolvedValue(SCREENSHOT)
  // The server answers a PATCH with the whole updated row.
  userFeedbackAdminApi.update.mockImplementation((id, patch) => {
    const row = [UNREAD, READ].find((r) => r.id === id)
    return Promise.resolve({ ...row, ...patch })
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// What the sidebar would show, read straight off the shared badge state.
function BadgeProbe() {
  const { count } = useFeedbackBadge()
  return <output aria-label="badge">{count === undefined ? '' : String(count)}</output>
}

async function renderLoaded() {
  render(
    <FeedbackBadgeProvider>
      <FeedbackAdminPage />
      <BadgeProbe />
    </FeedbackBadgeProvider>,
  )
  await screen.findByText('Shopping list crashes')
  await waitFor(() => expect(screen.getByLabelText('badge')).toHaveTextContent('2'))
}

const list = () => screen.getByRole('list', { name: 'Feedback' })
const rowFor = (ref) => within(list()).getByText(ref).closest('li')
const openRow = (ref) => fireEvent.click(within(rowFor(ref)).getByRole('button'))
const detail = (title) => screen.findByRole('region', { name: title })

// ---------------------------------------------------------------------------
// The list
// ---------------------------------------------------------------------------

test('each row shows ref, title, type, status, priority, tags, author and date', async () => {
  await renderLoaded()

  const row = rowFor('FB-7')
  expect(row).toHaveTextContent('Shopping list crashes')
  expect(row).toHaveTextContent('Not working')
  expect(row).toHaveTextContent('Open')
  expect(row).toHaveTextContent('High priority')
  expect(row).toHaveTextContent('mobile')
  expect(row).toHaveTextContent('shopping-list')
  expect(row).toHaveTextContent('anna')
  expect(row).toHaveTextContent(shownDate(UNREAD.created_at))
})

test('only an unread row carries the unread marker', async () => {
  await renderLoaded()

  expect(within(rowFor('FB-7')).getByLabelText('Unread')).toBeInTheDocument()
  expect(within(rowFor('FB-5')).queryByLabelText('Unread')).not.toBeInTheDocument()
})

test('a row whose author deleted their account says so', async () => {
  await renderLoaded()

  expect(rowFor('FB-5')).toHaveTextContent('Deleted account')
  expect(rowFor('FB-5')).toHaveTextContent('In progress')
})

test('an empty list says there is nothing to read', async () => {
  userFeedbackAdminApi.list.mockResolvedValue([])
  render(<FeedbackAdminPage />)

  expect(await screen.findByText(/no feedback/i)).toBeInTheDocument()
})

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

test('filtering by status asks the server for that status', async () => {
  await renderLoaded()

  fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'open' } })

  await waitFor(() =>
    expect(userFeedbackAdminApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'open' })),
  )
})

test('the tag filter offers the vocabulary and asks the server for that tag', async () => {
  await renderLoaded()

  const tagFilter = screen.getByLabelText('Filter by tag')
  await within(tagFilter).findByRole('option', { name: 'shopping-list' })
  fireEvent.change(tagFilter, { target: { value: 'mobile' } })

  await waitFor(() =>
    expect(userFeedbackAdminApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ tag: 'mobile' })),
  )
})

test('type and priority filters reach the server too', async () => {
  await renderLoaded()

  fireEvent.change(screen.getByLabelText('Filter by type'), { target: { value: 'request' } })
  fireEvent.change(screen.getByLabelText('Filter by priority'), { target: { value: 'high' } })

  await waitFor(() =>
    expect(userFeedbackAdminApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ type: 'request', priority: 'high' }),
    ),
  )
})

test('the unread-only toggle asks for unseen rows', async () => {
  await renderLoaded()

  const toggle = screen.getByRole('button', { name: 'Unread only' })
  fireEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-pressed', 'true')
  await waitFor(() =>
    expect(userFeedbackAdminApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ seen: false })),
  )
})

// ---------------------------------------------------------------------------
// Load failure
// ---------------------------------------------------------------------------

test('a failed load says so, and trying again loads the rows', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  userFeedbackAdminApi.list.mockRejectedValueOnce(new Error('down'))
  render(<FeedbackAdminPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t load the feedback.')
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('Shopping list crashes')).toBeInTheDocument()
})

// ---------------------------------------------------------------------------
// Reading an item
// ---------------------------------------------------------------------------

test('the detail pane invites a choice until a row is opened', async () => {
  await renderLoaded()

  expect(screen.getByText(/select an item/i)).toBeInTheDocument()
})

test('opening an unread row marks it read and takes one off the badge', async () => {
  await renderLoaded()

  openRow('FB-7')

  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenCalledWith(7, { seen: true }))
  await waitFor(() => expect(screen.getByLabelText('badge')).toHaveTextContent('1'))
  expect(within(rowFor('FB-7')).queryByLabelText('Unread')).not.toBeInTheDocument()
})

test('opening a row already read changes nothing on the server', async () => {
  await renderLoaded()

  openRow('FB-5')

  await detail('Dark mode please')
  expect(userFeedbackAdminApi.update).not.toHaveBeenCalled()
  expect(screen.getByLabelText('badge')).toHaveTextContent('2')
})

test('the detail shows the full item and its captured context', async () => {
  await renderLoaded()

  openRow('FB-7')

  const pane = await detail('Shopping list crashes')
  expect(pane).toHaveTextContent('FB-7')
  expect(pane).toHaveTextContent('It crashes when I tick the last item.')
  expect(pane).toHaveTextContent('anna')
  expect(pane).toHaveTextContent('anna@example.com')
  expect(pane).toHaveTextContent(shownDate(UNREAD.created_at))
  expect(pane).toHaveTextContent(shownDate(UNREAD.updated_at))
  expect(pane).toHaveTextContent('/shopping-list')
  expect(pane).toHaveTextContent('390 px')
  expect(pane).toHaveTextContent('Mozilla/5.0 (iPhone)')
})

test('marking a read item unread puts one back on the badge', async () => {
  await renderLoaded()
  openRow('FB-5')
  const pane = await detail('Dark mode please')

  fireEvent.click(within(pane).getByRole('button', { name: 'Mark unread' }))

  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenCalledWith(5, { seen: false }))
  await waitFor(() => expect(screen.getByLabelText('badge')).toHaveTextContent('3'))
  expect(within(rowFor('FB-5')).getByLabelText('Unread')).toBeInTheDocument()
})

// ---------------------------------------------------------------------------
// Screenshot
// ---------------------------------------------------------------------------

test('a screenshot is fetched with the token and shown from a blob url', async () => {
  await renderLoaded()

  openRow('FB-7')

  const image = await screen.findByRole('img', { name: 'Screenshot attached to FB-7' })
  expect(image).toHaveAttribute('src', 'blob:screenshot-7')
  expect(userFeedbackAdminApi.screenshot).toHaveBeenCalledWith(7)
  expect(URL.createObjectURL).toHaveBeenCalledWith(SCREENSHOT)
})

test('an item without a screenshot fetches none', async () => {
  await renderLoaded()

  openRow('FB-5')

  await detail('Dark mode please')
  expect(userFeedbackAdminApi.screenshot).not.toHaveBeenCalled()
  expect(screen.queryByRole('img', { name: /screenshot/i })).not.toBeInTheDocument()
})

test('moving to another item releases the previous screenshot url', async () => {
  await renderLoaded()
  openRow('FB-7')
  await screen.findByRole('img', { name: 'Screenshot attached to FB-7' })

  openRow('FB-5')

  await detail('Dark mode please')
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:screenshot-7')
})

// ---------------------------------------------------------------------------
// Triage controls
// ---------------------------------------------------------------------------

test('changing the status saves it and updates the row', async () => {
  await renderLoaded()
  openRow('FB-5')
  const pane = await detail('Dark mode please')

  fireEvent.change(within(pane).getByLabelText('Status'), { target: { value: 'closed_fixed' } })

  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenCalledWith(5, { status: 'closed_fixed' }))
  await waitFor(() => expect(rowFor('FB-5')).toHaveTextContent('Closed: fixed'))
})

test('changing the priority saves it', async () => {
  await renderLoaded()
  openRow('FB-5')
  const pane = await detail('Dark mode please')

  fireEvent.change(within(pane).getByLabelText('Priority'), { target: { value: 'low' } })

  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenCalledWith(5, { priority: 'low' }))
})

test('notes are saved only by the Save button, and blank notes clear them', async () => {
  await renderLoaded()
  openRow('FB-5')
  const pane = await detail('Dark mode please')
  const notes = within(pane).getByLabelText('Admin notes')
  expect(notes).toHaveValue('Later this year')

  fireEvent.change(notes, { target: { value: '  Duplicate of FB-2  ' } })
  expect(userFeedbackAdminApi.update).not.toHaveBeenCalled()
  fireEvent.click(within(pane).getByRole('button', { name: 'Save notes' }))
  await waitFor(() =>
    expect(userFeedbackAdminApi.update).toHaveBeenCalledWith(5, { admin_notes: 'Duplicate of FB-2' }),
  )

  fireEvent.change(notes, { target: { value: '   ' } })
  fireEvent.click(within(pane).getByRole('button', { name: 'Save notes' }))
  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenLastCalledWith(5, { admin_notes: null }))
})

test('typing a new tag adds it to the whole set, and the vocabulary is re-read', async () => {
  await renderLoaded()
  openRow('FB-7')
  const pane = await detail('Shopping list crashes')
  userFeedbackAdminApi.listTags.mockClear()

  const input = within(pane).getByLabelText('Add a tag')
  fireEvent.change(input, { target: { value: '  Crash  Report ' } })
  fireEvent.click(within(pane).getByRole('button', { name: 'Add tag' }))

  await waitFor(() =>
    expect(userFeedbackAdminApi.update).toHaveBeenLastCalledWith(7, {
      tags: ['mobile', 'shopping-list', 'crash report'],
    }),
  )
  await waitFor(() => expect(input).toHaveValue(''))
  expect(userFeedbackAdminApi.listTags).toHaveBeenCalled()
})

test('a failed tag add keeps the typed name', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  await renderLoaded()
  openRow('FB-5')
  const pane = await detail('Dark mode please')
  userFeedbackAdminApi.update.mockRejectedValueOnce(new Error('Too many requests'))

  const input = within(pane).getByLabelText('Add a tag')
  fireEvent.change(input, { target: { value: 'ui' } })
  fireEvent.click(within(pane).getByRole('button', { name: 'Add tag' }))

  await screen.findByRole('alert')
  expect(input).toHaveValue('ui')
})

test('a tag the item already has is not sent again', async () => {
  await renderLoaded()
  openRow('FB-7')
  const pane = await detail('Shopping list crashes')
  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenCalledTimes(1)) // the read mark

  fireEvent.change(within(pane).getByLabelText('Add a tag'), { target: { value: 'Mobile' } })
  fireEvent.click(within(pane).getByRole('button', { name: 'Add tag' }))

  expect(userFeedbackAdminApi.update).toHaveBeenCalledTimes(1)
})

test('removing a tag sends the set without it', async () => {
  await renderLoaded()
  openRow('FB-7')
  const pane = await detail('Shopping list crashes')

  fireEvent.click(within(pane).getByRole('button', { name: 'Remove tag mobile' }))

  await waitFor(() => expect(userFeedbackAdminApi.update).toHaveBeenLastCalledWith(7, { tags: ['shopping-list'] }))
})

test('a failed save is announced', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  await renderLoaded()
  openRow('FB-5')
  const pane = await detail('Dark mode please')
  userFeedbackAdminApi.update.mockRejectedValueOnce(new Error('Too many requests'))

  fireEvent.change(within(pane).getByLabelText('Priority'), { target: { value: 'high' } })

  expect(await screen.findByRole('alert')).toHaveTextContent(/Couldn’t save the priority: Too many requests\./)
})

// ---------------------------------------------------------------------------
// Phone width: list, then detail
// ---------------------------------------------------------------------------

test('on a phone the list gives way to the detail, and back returns to it', async () => {
  stubViewport(true)
  await renderLoaded()
  expect(screen.queryByText(/select an item/i)).not.toBeInTheDocument()

  openRow('FB-5')

  await detail('Dark mode please')
  expect(screen.queryByRole('list', { name: 'Feedback' })).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Back to the list' }))

  expect(screen.getByRole('list', { name: 'Feedback' })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Dark mode please' })).not.toBeInTheDocument()
})
