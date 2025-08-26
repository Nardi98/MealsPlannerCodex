import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppContext } from '../../App'
import NewPlan from '../NewPlan'
import { vi, afterEach, test, expect } from 'vitest'

vi.mock('../../api', () => ({
  mealPlansApi: {
    generate: vi.fn(),
    create: vi.fn(),
  },
}))

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('sends plan with main and side ids', async () => {
  const today = new Date().toISOString().slice(0, 10)
  const generated = {
    [today]: [
      [
        { id: 1, title: 'A' },
        { id: 2, title: 'B' },
      ],
      [
        { id: 3, title: 'C' },
      ],
    ],
  }
  const { mealPlansApi } = await import('../../api')
  mealPlansApi.generate.mockResolvedValue(generated)
  mealPlansApi.create.mockResolvedValue({})

  const setPlan = vi.fn()
  const value = { plan: {}, setPlan, recipes: [], setRecipes: () => {} }
  render(
    <AppContext.Provider value={value}>
      <MemoryRouter>
        <NewPlan />
      </MemoryRouter>
    </AppContext.Provider>
  )
  fireEvent.click(screen.getByText('Generate Plan'))

  await waitFor(() => expect(mealPlansApi.create).toHaveBeenCalled())
  expect(setPlan).toHaveBeenCalledWith({ [today]: ['A', 'C'] })
  expect(mealPlansApi.create).toHaveBeenCalledWith(
    expect.objectContaining({
      plan_date: today,
      plan: {
        [today]: [
          { main: 1, sides: [2] },
          { main: 3, sides: [] },
        ],
      },
    })
  )
})

