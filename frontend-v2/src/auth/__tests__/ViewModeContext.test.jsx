/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { ViewModeProvider, useViewMode } from '../ViewModeContext'

let authState

vi.mock('../AuthContext', () => ({
  useAuth: () => authState,
}))

afterEach(cleanup)

function Probe() {
  const { mode, isAdminMode, canAdmin, setMode } = useViewMode()
  return (
    <div>
      <div>{`mode:${mode}`}</div>
      <div>{`admin:${String(isAdminMode)}`}</div>
      <div>{`can:${String(canAdmin)}`}</div>
      <button type="button" onClick={() => setMode('admin')}>
        go admin
      </button>
      <button type="button" onClick={() => setMode('user')}>
        go user
      </button>
    </div>
  )
}

function renderAs(user) {
  authState = { user }
  return render(
    <ViewModeProvider>
      <Probe />
    </ViewModeProvider>,
  )
}

test('every account starts in user mode', () => {
  renderAs({ email: 'a@x.test', is_admin: true })

  expect(screen.getByText('mode:user')).toBeInTheDocument()
  expect(screen.getByText('admin:false')).toBeInTheDocument()
})

test('an admin can switch to admin mode and back', async () => {
  renderAs({ email: 'a@x.test', is_admin: true })

  expect(screen.getByText('can:true')).toBeInTheDocument()

  await userEvent.click(screen.getByText('go admin'))
  expect(screen.getByText('mode:admin')).toBeInTheDocument()
  expect(screen.getByText('admin:true')).toBeInTheDocument()

  await userEvent.click(screen.getByText('go user'))
  expect(screen.getByText('admin:false')).toBeInTheDocument()
})

test.each([
  ['is_admin missing', { email: 'a@x.test' }],
  ['is_admin false', { email: 'a@x.test', is_admin: false }],
  ['is_admin truthy but not true', { email: 'a@x.test', is_admin: 'yes' }],
  ['no account at all', null],
])('%s can never reach admin mode', async (_label, user) => {
  renderAs(user)

  expect(screen.getByText('can:false')).toBeInTheDocument()

  await userEvent.click(screen.getByText('go admin'))

  expect(screen.getByText('mode:user')).toBeInTheDocument()
  expect(screen.getByText('admin:false')).toBeInTheDocument()
})

test('losing the admin flag drops an active admin mode', async () => {
  const { rerender } = renderAs({ email: 'a@x.test', is_admin: true })
  await userEvent.click(screen.getByText('go admin'))
  expect(screen.getByText('admin:true')).toBeInTheDocument()

  authState = { user: { email: 'a@x.test', is_admin: false } }
  rerender(
    <ViewModeProvider>
      <Probe />
    </ViewModeProvider>,
  )

  expect(screen.getByText('admin:false')).toBeInTheDocument()
})

test('without a provider everything reads as a plain user', () => {
  authState = { user: { email: 'a@x.test', is_admin: true } }
  render(<Probe />)

  expect(screen.getByText('mode:user')).toBeInTheDocument()
  expect(screen.getByText('admin:false')).toBeInTheDocument()
  expect(screen.getByText('can:false')).toBeInTheDocument()
})
