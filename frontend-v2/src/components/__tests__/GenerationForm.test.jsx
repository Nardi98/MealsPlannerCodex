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
