/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import MealPlanCalendar from '../MealPlanCalendar'

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
