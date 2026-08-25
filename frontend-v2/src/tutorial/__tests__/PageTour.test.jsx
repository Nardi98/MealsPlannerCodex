/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
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

// The reported bug: the first Recipes step anchored on the whole recipe grid,
// and the bubble was placed below its bottom edge — thousands of pixels under a
// viewport that `position: fixed` means scrolling can never reach.
function stubRect(selector, box) {
  const el = document.querySelector(selector)
  el.getBoundingClientRect = () => ({
    top: 0, left: 0, width: 0, height: 0, bottom: 0, right: 0, x: 0, y: 0, ...box,
  })
  return el
}

// The hook coalesces measurements onto an animation frame; run them inline so a
// test can assert on the position that a scroll or resize produced.
function withSyncFrames(body) {
  const real = window.requestAnimationFrame
  window.requestAnimationFrame = (cb) => {
    cb(0)
    return 1
  }
  try {
    body()
  } finally {
    window.requestAnimationFrame = real
  }
}

test('a target taller than the window still leaves the bubble on screen', () => {
  withSyncFrames(() => {
    renderTour()
    stubRect('[data-tour="one"]', { top: 100, left: 40, width: 900, height: 3000 })
    act(() => {
      fireEvent.scroll(window)
    })
    const top = parseFloat(screen.getByRole('dialog').style.top)
    expect(top).toBeGreaterThanOrEqual(0)
    expect(top + 190).toBeLessThanOrEqual(window.innerHeight)
  })
})

test('the bubble is placed by its measured height, not the estimate', () => {
  // A step with long copy renders taller than the 190px estimate; placed by the
  // estimate it hangs off the bottom of the window.
  const real = Element.prototype.getBoundingClientRect
  Element.prototype.getBoundingClientRect = function boxed() {
    if (this.getAttribute('role') === 'dialog') {
      return { top: 0, left: 0, width: 300, height: 600, bottom: 600, right: 300, x: 0, y: 0 }
    }
    return real.call(this)
  }
  try {
    withSyncFrames(() => {
      renderTour()
      stubRect('[data-tour="one"]', { top: 300, left: 40, width: 120, height: 40 })
      act(() => {
        fireEvent.scroll(window)
      })
      expect(parseFloat(screen.getByRole('dialog').style.top) + 600).toBeLessThanOrEqual(window.innerHeight)
    })
  } finally {
    Element.prototype.getBoundingClientRect = real
  }
})
