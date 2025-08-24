import React, { useState } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PlanView from '../PlanView'
import { AppContext } from '../../App'
import { vi, afterEach, test, expect } from 'vitest'

function renderWithPlan(initialPlan) {
  function Wrapper({ children }) {
    const [plan, setPlan] = useState(initialPlan)
    const value = { plan, setPlan, recipes: [], setRecipes: () => {} }
    return <AppContext.Provider value={value}>{children}</AppContext.Provider>
  }
  return render(
    <Wrapper>
      <PlanView />
    </Wrapper>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

test('accept disables further actions', async () => {
  global.fetch = vi.fn((url) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/feedback/accept')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': ['A'] })
  const btn = await screen.findByText('Accept')
  fireEvent.click(btn)
  await waitFor(() => expect(screen.getByText('Accepted')).toBeInTheDocument())
})

test('reject replaces meal with server suggestion', async () => {
  global.fetch = vi.fn((url) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/feedback/reject')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ replacement: 'B' }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([{ id: 1, title: 'B' }]) })
    }
    if (url.endsWith('/meal-plans')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  })

  renderWithPlan({ '2024-01-01': ['A'] })
  const btn = await screen.findByText('Reject')
  fireEvent.click(btn)
  await waitFor(() => expect(screen.getByText('B')).toBeInTheDocument())
})

test('leftover age warning respects keep_days', async () => {
  global.fetch = vi.fn((url) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })
  renderWithPlan({
    '2024-01-01': ['A'],
    '2024-01-03': ['A (leftover)'],
  })
  await screen.findByText('A (leftover)')
  expect(
    screen.getByText('A (leftover) is 2 days old (max 1)')
  ).toBeInTheDocument()
})
