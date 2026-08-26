/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import GenerationForm from '../GenerationForm'
import { HOVER_DELAY_MS } from '../SettingTooltip'
import { SETTING_HELP } from '../settingHelp'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  cleanup()
})

const baseForm = {
  start: '2024-01-01',
  end: '2024-01-07',
  meals_per_day: 2,
  epsilon: 0.25,
  leftovers: 'some',
  seasonality: 'prefer',
  recency: 'medium',
  avoid_tags: [],
  reduce_tags: [],
  fridge: [],
}

const renderForm = (props = {}) =>
  render(
    <GenerationForm
      form={baseForm}
      tags={[]}
      message=""
      error=""
      onChange={() => {}}
      onRangeChange={() => {}}
      onPresetChange={() => {}}
      onAvoidChange={() => {}}
      onReduceChange={() => {}}
      onFridgeChange={() => {}}
      ingredients={[]}
      onSubmit={(e) => e.preventDefault()}
      {...props}
    />
  )

test('renders meals-per-day as a segmented control with 1 meal and 2 meals options', () => {
  renderForm()
  const list = screen.getByRole('tablist', { name: /meals per day/i })
  expect(list).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: /1 meal/i })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: /2 meals/i })).toBeInTheDocument()
})

test('reflects the current meals_per_day value as the selected tab', () => {
  renderForm({ form: { ...baseForm, meals_per_day: 1 } })
  expect(screen.getByRole('tab', { name: /1 meal/i })).toHaveAttribute(
    'aria-selected',
    'true'
  )
})

test('selecting a meals-per-day option calls onPresetChange with the numeric value', () => {
  const onPresetChange = vi.fn()
  renderForm({ onPresetChange })
  fireEvent.click(screen.getByRole('tab', { name: /1 meal/i }))
  expect(onPresetChange).toHaveBeenCalledWith('meals_per_day', 1)
})

test('shows Settings and Your Fridge tabs with Settings active first', () => {
  renderForm()
  expect(screen.getByRole('tab', { name: /^settings$/i })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: /your fridge/i })).toBeInTheDocument()
  // Fridge content is hidden until the tab is selected.
  expect(screen.queryByPlaceholderText(/search ingredients/i)).not.toBeInTheDocument()
})

test('switching to the fridge tab reveals the ingredient picker', () => {
  renderForm()
  fireEvent.click(screen.getByRole('tab', { name: /your fridge/i }))
  expect(screen.getByPlaceholderText(/search ingredients/i)).toBeInTheDocument()
})

test('the generate button is available regardless of the active tab', () => {
  renderForm()
  fireEvent.click(screen.getByRole('tab', { name: /your fridge/i }))
  expect(screen.getByRole('button', { name: /generate plan/i })).toBeInTheDocument()
})

test('marks its tab strip as the tutorial anchor, so the tour points at a strip and not the whole card', () => {
  const { container } = renderForm()
  expect(container.querySelectorAll('[data-tour="mealplan-tabs"]')).toHaveLength(1)
})

// --- per-setting help tooltips ---------------------------------------------

const hoverFor = async (node, ms) => {
  fireEvent.pointerEnter(node)
  await act(async () => {
    vi.advanceTimersByTime(ms)
  })
}

// Each control, by the text you can find it from and the help key it explains.
const SETTINGS = [
  ['Plan dates', 'dates'],
  ['Meals per day', 'meals_per_day'],
  ['Recommendation style', 'epsilon'],
  ['Leftovers', 'leftovers'],
  ['Seasonality', 'seasonality'],
  ['Variety', 'recency'],
  ['Avoid tags', 'avoid_tags'],
  ['Reduce tags', 'reduce_tags'],
]

test.each(SETTINGS)('resting on %s explains what it does', async (label, key) => {
  renderForm()
  const wrapper = screen.getByText(label).closest('[data-setting-tooltip]')
  expect(wrapper).not.toBeNull()
  await hoverFor(wrapper, HOVER_DELAY_MS)
  expect(screen.getByRole('tooltip')).toHaveTextContent(SETTING_HELP[key].body.slice(0, 30))
})

test('the fridge selector is explained too', async () => {
  const { container } = renderForm()
  fireEvent.click(screen.getByRole('tab', { name: 'Your Fridge' }))
  const wrapper = container.querySelector('[data-setting-tooltip]')
  await hoverFor(wrapper, HOVER_DELAY_MS)
  expect(screen.getByRole('tooltip')).toHaveTextContent(SETTING_HELP.fridge.body.slice(0, 30))
})
