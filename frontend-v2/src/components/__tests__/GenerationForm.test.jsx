/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import GenerationForm from '../GenerationForm'

afterEach(() => {
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
