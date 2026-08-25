/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, expect, test } from 'vitest'
import { PageTour } from '../PageTour'
import { isTourDone, markTourDone } from '../tourStorage'

const STEPS = [
  { target: '[data-tour="one"]', title: 'First thing', body: 'one', placement: 'bottom' },
  { target: '[data-tour="two"]', title: 'Second thing', body: 'two', placement: 'bottom' },
]

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  cleanup()
  document.body.innerHTML = ''
})

function renderTour(props = {}) {
  return render(
    <div>
      <div data-tour="one">anchor</div>
      <PageTour id="recipes" steps={STEPS} {...props} />
    </div>,
  )
}

test('runs on a first visit and walks to the end', () => {
  renderTour()
  expect(screen.getByText('First thing')).toBeInTheDocument()
  expect(screen.getByTestId('tour-overlay')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByText('Second thing')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Done' }))
  expect(screen.queryByTestId('tour-overlay')).not.toBeInTheDocument()
  expect(isTourDone('recipes')).toBe(true)
})

test('stays away on a return visit', () => {
  markTourDone('recipes')
  renderTour()
  expect(screen.queryByTestId('tour-overlay')).not.toBeInTheDocument()
})

test('waits while disabled, so a first-run modal can go first', () => {
  const { rerender } = render(<PageTour id="recipes" steps={STEPS} enabled={false} />)
  expect(screen.queryByTestId('tour-overlay')).not.toBeInTheDocument()
  rerender(<PageTour id="recipes" steps={STEPS} enabled />)
  expect(screen.getByText('First thing')).toBeInTheDocument()
})

test('skipping silences the other pages too', () => {
  renderTour()
  fireEvent.click(screen.getByRole('button', { name: 'Skip tutorial' }))
  expect(screen.queryByTestId('tour-overlay')).not.toBeInTheDocument()
  expect(isTourDone('meal-plan')).toBe(true)
})

test('renders above the app, in a portal on the body', () => {
  const { container } = renderTour()
  expect(container.querySelector('[data-testid="tour-overlay"]')).toBe(null)
  expect(document.body.querySelector('[data-testid="tour-overlay"]')).not.toBe(null)
})
