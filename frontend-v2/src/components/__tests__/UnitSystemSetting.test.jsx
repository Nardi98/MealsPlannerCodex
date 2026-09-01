/** @vitest-environment jsdom */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import UnitSystemSetting from '../UnitSystemSetting'
import { authApi } from '../../api/authApi'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/authApi', () => ({
  authApi: { setUnitSystem: vi.fn() },
}))
vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: { switchPreferredDimension: vi.fn() },
}))

beforeEach(() => {
  authApi.setUnitSystem.mockResolvedValue({ unit_system: 'us' })
  ingredientsApi.switchPreferredDimension.mockResolvedValue({
    switched: ['Flour'],
    skipped: ['Salt'],
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const setup = (props = {}) =>
  render(<UnitSystemSetting value="metric" onChange={() => {}} {...props} />)

test('switching takes effect with no save step, because it touches no data', async () => {
  const onChange = vi.fn()
  setup({ onChange })

  fireEvent.click(screen.getByRole('tab', { name: 'US' }))

  await waitFor(() => expect(authApi.setUnitSystem).toHaveBeenCalledWith('us'))
  expect(onChange).toHaveBeenCalledWith('us')
})

test('offers once to move the pantry to the way US recipes measure', async () => {
  setup()

  fireEvent.click(screen.getByRole('tab', { name: 'US' }))

  expect(await screen.findByText(/switch your ingredients/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /switch/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /keep as they are/i })).toBeInTheDocument()
})

test('accepting flips only the ingredients the conversions support', async () => {
  setup()
  fireEvent.click(screen.getByRole('tab', { name: 'US' }))
  fireEvent.click(await screen.findByRole('button', { name: /^Switch$/ }))

  await waitFor(() =>
    expect(ingredientsApi.switchPreferredDimension).toHaveBeenCalledWith('volume'),
  )
})

test('reports plainly what it could not switch and does not nag', async () => {
  setup()
  fireEvent.click(screen.getByRole('tab', { name: 'US' }))
  fireEvent.click(await screen.findByRole('button', { name: /^Switch$/ }))

  expect(await screen.findByText(/Salt/)).toBeInTheDocument()
})

test('declining changes nothing but the rendering units', async () => {
  setup()
  fireEvent.click(screen.getByRole('tab', { name: 'US' }))
  fireEvent.click(await screen.findByRole('button', { name: /keep as they are/i }))

  expect(ingredientsApi.switchPreferredDimension).not.toHaveBeenCalled()
  await waitFor(() => expect(authApi.setUnitSystem).toHaveBeenCalled())
})

test('going back to metric offers to weigh things again', async () => {
  setup({ value: 'us' })

  fireEvent.click(screen.getByRole('tab', { name: 'Metric' }))
  fireEvent.click(await screen.findByRole('button', { name: /^Switch$/ }))

  await waitFor(() =>
    expect(ingredientsApi.switchPreferredDimension).toHaveBeenCalledWith('mass'),
  )
})

test('does not raise the popup when nothing is switchable', async () => {
  ingredientsApi.switchPreferredDimension.mockResolvedValue({
    switched: [],
    skipped: [],
  })
  setup({ switchable: false })

  fireEvent.click(screen.getByRole('tab', { name: 'US' }))

  await waitFor(() => expect(authApi.setUnitSystem).toHaveBeenCalled())
  expect(screen.queryByText(/switch your ingredients/i)).toBeNull()
})
