/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import MealActionModal from '../MealActionModal'

afterEach(() => cleanup())

vi.mock('../../api/recipesApi', () => ({
  recipesApi: { list: vi.fn().mockResolvedValue([]) },
}))
vi.mock('../../api/tagsApi', () => ({
  tagsApi: { list: vi.fn().mockResolvedValue([]) },
}))

function renderModal(props = {}) {
  return render(
    <MealActionModal
      date="2024-01-01"
      meal="lunch"
      recipe="Pasta al pesto"
      sides={['Insalata mista']}
      accepted={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onSwap={vi.fn()}
      onAddSide={vi.fn()}
      onRejectSide={vi.fn()}
      onRemoveSide={vi.fn()}
      onSwapSide={vi.fn()}
      onClose={vi.fn()}
      {...props}
    />,
  )
}

// The close control was a bare 20px icon with no accessible name.
test('the close control is named and finger-sized', () => {
  const onClose = vi.fn()
  renderModal({ onClose })

  const close = screen.getByRole('button', { name: 'Close' })
  expect(close.className).toContain('h-11')
  fireEvent.click(close)
  expect(onClose).toHaveBeenCalled()
})

// Side-dish actions were unlabelled 16px SVGs, so neither reachable by
// keyboard nor reliably tappable.
test('side dish actions are named buttons at a full tap target', () => {
  const onRemoveSide = vi.fn()
  const onRejectSide = vi.fn()
  renderModal({ onRemoveSide, onRejectSide })

  const remove = screen.getByRole('button', { name: 'Remove side dish Insalata mista' })
  const reject = screen.getByRole('button', { name: 'Reject side dish Insalata mista' })
  expect(remove.className).toContain('h-11')
  expect(reject.className).toContain('h-11')

  fireEvent.click(remove)
  expect(onRemoveSide).toHaveBeenCalledWith(0)
  fireEvent.click(reject)
  expect(onRejectSide).toHaveBeenCalledWith(0)
})

test('the tag filter toggles are named', () => {
  renderModal()
  fireEvent.click(screen.getByRole('button', { name: /^Swap$/ }))
  expect(screen.getByRole('button', { name: /filter recipes by tag/i })).toBeTruthy()
})
