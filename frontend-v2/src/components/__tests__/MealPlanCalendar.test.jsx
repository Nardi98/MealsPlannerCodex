/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import MealPlanCalendar from '../MealPlanCalendar'
import { stubViewport } from '../../test/stubViewport'

afterEach(() => cleanup())

const day = new Date('2024-01-01T00:00:00')
const iso = '2024-01-01'
const fmt = () => iso

function renderCalendar(props = {}) {
  const plan = {
    [iso]: [
      { recipe: 'Lunch A', side_recipes: [], accepted: true, leftover: false },
      { recipe: 'Dinner B', side_recipes: [], accepted: false, leftover: false },
    ],
  }
  return render(
    <MealPlanCalendar
      weekDays={[day]}
      plan={plan}
      fmt={fmt}
      isToday={() => false}
      onSelectCell={vi.fn()}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onChangeWeek={vi.fn()}
      onArmSwap={vi.fn()}
      armedCell={null}
      {...props}
    />,
  )
}

test('renders a swap control on every filled cell, even accepted ones', () => {
  renderCalendar()
  // Two filled meals (accepted lunch + un-accepted dinner) -> two swap controls.
  expect(screen.getAllByLabelText(/swap meal/i)).toHaveLength(2)
})

test('clicking the swap control arms that cell', () => {
  const onArmSwap = vi.fn()
  renderCalendar({ onArmSwap })
  fireEvent.click(screen.getAllByLabelText(/swap meal/i)[0])
  expect(onArmSwap).toHaveBeenCalledWith({ date: iso, mealIndex: 0 })
})

test('while armed, clicking a second square completes the swap (not select)', () => {
  const onArmSwap = vi.fn()
  const onSelectCell = vi.fn()
  renderCalendar({
    onArmSwap,
    onSelectCell,
    armedCell: { date: iso, mealIndex: 0 },
  })
  fireEvent.click(screen.getByText('Dinner B').closest('div[data-cell]'))
  expect(onArmSwap).toHaveBeenCalledWith({ date: iso, mealIndex: 1 })
  expect(onSelectCell).not.toHaveBeenCalled()
})

test('with nothing armed, clicking a square selects it (opens modal)', () => {
  const onSelectCell = vi.fn()
  renderCalendar({ onSelectCell, armedCell: null })
  fireEvent.click(screen.getByText('Dinner B').closest('div[data-cell]'))
  expect(onSelectCell).toHaveBeenCalledWith({ date: iso, mealIndex: 1 })
})

test('the armed cell is tinted yellow', () => {
  renderCalendar({ armedCell: { date: iso, mealIndex: 0 } })
  const armed = screen.getByText('Lunch A').closest('div[data-cell]')
  expect(armed.getAttribute('style')).toMatch(/255, ?185, ?2/)
})

test('marks the first lunch cell as the tutorial anchor, so the tour points at one meal', () => {
  const { container } = renderCalendar()
  const anchors = container.querySelectorAll('[data-tour="mealplan-cell"]')
  expect(anchors).toHaveLength(1)
  expect(anchors[0].textContent).toContain('Lunch A')
})

// --- Mobile layout ----------------------------------------------------------
//
// A 7-day x 2-meal grid gives each day ~40px on a phone, so below `md` the
// calendar stacks into one card per day instead. jsdom does not evaluate media
// queries, hence the `matchMedia` stub rather than a class assertion.

test('stacks into one section per day on mobile instead of the week grid', () => {
  stubViewport(true)
  const { container } = renderCalendar()

  expect(container.querySelector('.grid-cols-8')).toBeNull()
  expect(screen.getAllByTestId('mealplan-day')).toHaveLength(1)
  // Each meal is labelled, since there is no longer a row header to read it from.
  expect(screen.getByText('Lunch')).toBeTruthy()
  expect(screen.getByText('Dinner')).toBeTruthy()
})

test('keeps the week grid on desktop', () => {
  stubViewport(false)
  const { container } = renderCalendar()

  expect(container.querySelector('.grid-cols-8')).not.toBeNull()
  expect(screen.queryAllByTestId('mealplan-day')).toHaveLength(0)
})

test('cell controls still work in the mobile layout', () => {
  stubViewport(true)
  const onArmSwap = vi.fn()
  renderCalendar({ onArmSwap })

  const swaps = screen.getAllByLabelText(/swap meal/i)
  expect(swaps).toHaveLength(2)
  fireEvent.click(swaps[1])
  expect(onArmSwap).toHaveBeenCalledWith({ date: iso, mealIndex: 1 })
})

test('keeps the tutorial anchors in the mobile layout', () => {
  stubViewport(true)
  const { container } = renderCalendar()

  expect(container.querySelector('[data-tour="mealplan-cell"]')).not.toBeNull()
  expect(container.querySelector('[data-tour="mealplan-week-nav"]')).not.toBeNull()
  expect(container.querySelector('[data-tour="mealplan-calendar"]')).not.toBeNull()
})
