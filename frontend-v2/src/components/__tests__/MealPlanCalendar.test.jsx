/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import MealPlanCalendar from '../MealPlanCalendar'
import { stubViewport } from '../../test/stubViewport'
import { formatWeekRange } from '../../lib/weekRange'

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

test('the armed cell is tinted yellow and outlined', () => {
  renderCalendar({ armedCell: { date: iso, mealIndex: 0 } })
  // The swap banner also names the armed meal, so scope to the grid cell.
  const armed = screen
    .getAllByText('Lunch A')
    .map((el) => el.closest('div[data-cell]'))
    .find(Boolean)
  expect(armed.getAttribute('style')).toMatch(/255, ?185, ?2/)
  // Colour alone is not a state cue: the armed cell is outlined too.
  expect(armed.getAttribute('style')).toMatch(/outline/)
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

// --- Day view, week strip and the view toggle -------------------------------
//
// The stacked mobile layout gave no sense of where you were in the week and no
// date context at all. Below `md` the calendar now opens on a single day, with
// a seven-day strip acting as both overview and navigator.

const week = Array.from({ length: 7 }, (_, i) => new Date(2024, 0, 1 + i))
const isoOf = (d) => `2024-01-0${d.getDate()}`

function renderWeek(props = {}) {
  const plan = {
    '2024-01-01': [
      { recipe: 'Lunch A', side_recipes: [], accepted: true, leftover: false },
      { recipe: 'Dinner B', side_recipes: [], accepted: false, leftover: false },
    ],
    '2024-01-03': [
      { recipe: 'Wednesday lunch', side_recipes: [], accepted: false, leftover: false },
    ],
  }
  return render(
    <MealPlanCalendar
      weekDays={week}
      plan={plan}
      fmt={isoOf}
      isToday={(d) => d.getDate() === 1}
      onSelectCell={vi.fn()}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onChangeWeek={vi.fn()}
      onArmSwap={vi.fn()}
      onCancelSwap={vi.fn()}
      onToday={vi.fn()}
      armedCell={null}
      {...props}
    />,
  )
}

test('day view shows one day and a seven-day strip to move between them', () => {
  stubViewport(true)
  window.localStorage.clear()
  renderWeek()

  expect(screen.getAllByTestId('day-strip-day')).toHaveLength(7)
  expect(screen.getAllByTestId('mealplan-day')).toHaveLength(1)
})

test('day view opens on today when today is inside the viewed week', () => {
  stubViewport(true)
  window.localStorage.clear()
  renderWeek()
  // The strip marks today for screen readers and the day header repeats it.
  expect(screen.getAllByText(/today/i).length).toBeGreaterThan(0)
  expect(screen.getByText('Lunch A')).toBeTruthy()
})

test('tapping a day in the strip switches the day shown', () => {
  stubViewport(true)
  window.localStorage.clear()
  renderWeek()

  expect(screen.queryByText('Wednesday lunch')).toBeNull()
  fireEvent.click(screen.getAllByTestId('day-strip-day')[2])
  expect(screen.getByText('Wednesday lunch')).toBeTruthy()
})

test('the week toggle shows every day and is remembered across remounts', () => {
  stubViewport(true)
  window.localStorage.clear()
  renderWeek()

  fireEvent.click(screen.getByRole('button', { name: 'Week' }))
  expect(screen.getAllByTestId('mealplan-day')).toHaveLength(7)

  cleanup()
  renderWeek()
  expect(screen.getAllByTestId('mealplan-day')).toHaveLength(7)
  window.localStorage.clear()
})

// --- The swap banner --------------------------------------------------------
//
// Arming used to be signalled by a yellow tint and nothing else, with no way
// out but pressing the same cell again.

test('arming a swap explains itself and offers a cancel', () => {
  stubViewport(false)
  const onCancelSwap = vi.fn()
  renderWeek({ armedCell: { date: '2024-01-01', mealIndex: 0 }, onCancelSwap })

  const banner = screen.getByTestId('swap-banner')
  expect(banner.textContent).toContain('Lunch A')
  fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
  expect(onCancelSwap).toHaveBeenCalled()
})

test('no banner is shown when nothing is armed', () => {
  stubViewport(false)
  renderWeek()
  expect(screen.queryByTestId('swap-banner')).toBeNull()
})

// --- Orientation and status -------------------------------------------------

test('states the week being viewed', () => {
  stubViewport(false)
  renderWeek()
  // The month name is locale-dependent, so compare against the formatter
  // itself. Previously there was no week label anywhere in the calendar.
  expect(formatWeekRange(week)).toMatch(/1/)
  expect(screen.getByText(formatWeekRange(week))).toBeTruthy()
})

test('shows accepted / pending as a labelled chip on desktop too', () => {
  stubViewport(false)
  renderWeek()
  expect(screen.getAllByText('Accepted').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Pending').length).toBeGreaterThan(0)
})

test('accept and reject controls are reachable by an accessible name', () => {
  stubViewport(false)
  const onAccept = vi.fn()
  renderWeek({ onAccept })

  fireEvent.click(screen.getByRole('button', { name: 'Accept Dinner B' }))
  expect(onAccept).toHaveBeenCalledWith({ date: '2024-01-01', mealIndex: 1 })
  expect(screen.getByRole('button', { name: 'Reject Dinner B' })).toBeTruthy()
})
