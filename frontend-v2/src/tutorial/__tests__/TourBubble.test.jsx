/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, test, vi } from 'vitest'
import { TourBubble } from '../TourBubble'

afterEach(cleanup)

function setup(props = {}) {
  const handlers = { onNext: vi.fn(), onBack: vi.fn(), onSkip: vi.fn() }
  render(
    <TourBubble
      title="Your recipe book"
      body="Everything you can cook lives here."
      index={0}
      total={4}
      isLast={false}
      {...handlers}
      {...props}
    />,
  )
  return handlers
}

test('shows the step copy', () => {
  setup()
  expect(screen.getByText('Your recipe book')).toBeInTheDocument()
  expect(screen.getByText('Everything you can cook lives here.')).toBeInTheDocument()
})

test('renders one dot per step and marks the current one', () => {
  setup({ index: 1, total: 4 })
  const dots = screen.getAllByTestId('tour-dot')
  expect(dots).toHaveLength(4)
  expect(screen.getByLabelText('Step 2 of 4')).toBeInTheDocument()
  expect(dots[1]).toHaveAttribute('data-current', 'true')
  expect(dots[0]).toHaveAttribute('data-current', 'false')
})

test('hides Back on the first step and shows it afterwards', () => {
  setup()
  expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument()
  cleanup()
  const handlers = setup({ index: 1 })
  fireEvent.click(screen.getByRole('button', { name: /back/i }))
  expect(handlers.onBack).toHaveBeenCalled()
})

test('the primary button says Next until the last step, where it says Done', () => {
  const handlers = setup()
  const next = screen.getByRole('button', { name: 'Next' })
  fireEvent.click(next)
  expect(handlers.onNext).toHaveBeenCalled()
  cleanup()
  setup({ index: 3, isLast: true })
  expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument()
})

test('Skip tutorial is offered on every step', () => {
  const handlers = setup()
  fireEvent.click(screen.getByRole('button', { name: 'Skip tutorial' }))
  expect(handlers.onSkip).toHaveBeenCalled()
})

test('draws the squiggly arrow when anchored, and omits it when centered', () => {
  setup({ arrow: 'up' })
  expect(screen.getByTestId('tour-arrow')).toBeInTheDocument()
  cleanup()
  setup({ arrow: null })
  expect(screen.queryByTestId('tour-arrow')).not.toBeInTheDocument()
})
