/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import NavDrawer from '../NavDrawer'

afterEach(cleanup)

function open(props = {}) {
  const onClose = vi.fn()
  render(
    <MemoryRouter>
      <NavDrawer open onClose={onClose} footer={<button type="button">Replay tutorial</button>} {...props} />
    </MemoryRouter>,
  )
  return onClose
}

test('renders nothing when closed', () => {
  render(
    <MemoryRouter>
      <NavDrawer open={false} onClose={vi.fn()} />
    </MemoryRouter>,
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('renders the navigation as a modal dialog when open', () => {
  open()
  const dialog = screen.getByRole('dialog')
  expect(dialog).toHaveAttribute('aria-modal', 'true')
  expect(screen.getByRole('button', { name: /meal plan/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /shopping list/i })).toBeInTheDocument()
})

test('renders the footer slot', () => {
  open()
  expect(screen.getByRole('button', { name: /replay tutorial/i })).toBeInTheDocument()
})

test('closes when the scrim is clicked', async () => {
  const onClose = open()
  await userEvent.click(screen.getByTestId('nav-drawer-scrim'))
  expect(onClose).toHaveBeenCalled()
})

test('closes when Escape is pressed', async () => {
  const onClose = open()
  await userEvent.keyboard('{Escape}')
  expect(onClose).toHaveBeenCalled()
})

test('closes after a navigation item is chosen', async () => {
  const onClose = open()
  await userEvent.click(screen.getByRole('button', { name: /ingredients/i }))
  expect(onClose).toHaveBeenCalled()
})

test('renders the header slot above the navigation', () => {
  render(
    <MemoryRouter>
      <NavDrawer
        open
        onClose={vi.fn()}
        header={<input placeholder="Search…" />}
        footer={<button type="button">Replay tutorial</button>}
      />
    </MemoryRouter>,
  )

  const dialog = screen.getByRole('dialog')
  const search = screen.getByPlaceholderText('Search…')
  const firstNavItem = screen.getByRole('button', { name: /recipes/i })

  expect(dialog).toContainElement(search)
  // Node order, not just presence: the search box is the first thing in the menu.
  expect(search.compareDocumentPosition(firstNavItem) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
