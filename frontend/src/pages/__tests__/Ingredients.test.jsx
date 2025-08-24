import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Ingredients from '../Ingredients'

afterEach(() => {
  vi.restoreAllMocks()
})

test('renders ingredient list', async () => {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve([
          {
            id: 1,
            name: 'Sugar',
            quantity: 1,
            unit: 'g',
            season_months: [],
            recipe_id: 1,
          },
        ]),
    })
  )
  render(<Ingredients />)
  await waitFor(() => expect(screen.getByDisplayValue('Sugar')).toBeInTheDocument())
})
