import React, { useState } from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PlanView from '../PlanView'
import { AppContext } from '../../App'
import { vi, afterEach, test, expect } from 'vitest'

function renderWithPlan(initialPlan) {
  function Wrapper({ children }) {
    const [plan, setPlan] = useState(initialPlan)
    const value = { plan, setPlan, recipes: [], setRecipes: () => {} }
    return (
      <AppContext.Provider value={value}>
        <MemoryRouter>{children}</MemoryRouter>
      </AppContext.Provider>
    )
  }
  return render(
    <Wrapper>
      <PlanView />
    </Wrapper>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
  cleanup()
})

test('accept disables further actions', async () => {
  global.fetch = vi.fn((url) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/meal-plans/accept')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': ['A'] })
  const btn = await screen.findByText('Accept')
  fireEvent.click(btn)
  await waitFor(() => expect(screen.getByText('Accepted')).toBeInTheDocument())
})

test('reject retries until unique suggestion', async () => {
  let calls = 0
  global.fetch = vi.fn((url) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/feedback/reject')) {
      calls += 1
      const replacement = calls === 1 ? 'C' : 'B'
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ replacement }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve([
          { id: 1, title: 'B' },
          { id: 2, title: 'C' },
        ]),
      })
    }
    if (url.endsWith('/meal-plans')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': ['A', 'C'] })
  const [btn] = await screen.findAllByText('Reject')
  fireEvent.click(btn)
  await waitFor(() => expect(screen.getByText('B')).toBeInTheDocument())
  expect(
    global.fetch.mock.calls.filter(([url]) => url.endsWith('/feedback/reject')).length
  ).toBe(2)
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

test('defaults date inputs to current week and loads that plan', async () => {
  const today = new Date()
  const day = today.getDay()
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((day + 6) % 7))
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  const fmt = (d) => d.toISOString().split('T')[0]
  const weekPlan = {
    [fmt(monday)]: [{ recipe: 'A', accepted: false }],
  }
  global.fetch = vi.fn((url) => {
    if (url.includes(`/plan?start_date=${fmt(monday)}&end_date=${fmt(sunday)}`)) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(weekPlan) })
    }
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })
  renderWithPlan({})
  const start = screen.getAllByLabelText('Start date')[0]
  const end = screen.getAllByLabelText('End date')[0]
  expect(start.value).toBe(fmt(monday))
  expect(end.value).toBe(fmt(sunday))
  await screen.findByText('A')
  expect(
    global.fetch.mock.calls.some(([u]) =>
      u.includes(`/plan?start_date=${fmt(monday)}&end_date=${fmt(sunday)}`)
    )
  ).toBe(true)
})

test('loads plan for date range', async () => {
  const rangePlan = {
    '2024-01-01': [{ recipe: 'A', accepted: false }],
    '2024-01-02': [{ recipe: 'B', accepted: false }],
  }
  const today = new Date()
  const day = today.getDay()
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((day + 6) % 7))
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  const fmt = (d) => d.toISOString().split('T')[0]
  global.fetch = vi.fn((url) => {
    if (url.includes('/plan?start_date=2024-01-01&end_date=2024-01-02')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(rangePlan) })
    }
    if (url.includes(`/plan?start_date=${fmt(monday)}&end_date=${fmt(sunday)}`)) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })
  renderWithPlan({})
  const start = screen.getAllByLabelText('Start date')[0]
  const end = screen.getAllByLabelText('End date')[0]
  fireEvent.change(start, { target: { value: '2024-01-01' } })
  fireEvent.change(end, { target: { value: '2024-01-02' } })
  fireEvent.click(screen.getAllByText('Load Plan')[0])
  await waitFor(() => expect(screen.getAllByText('A').length).toBeGreaterThan(0))
  expect(screen.getAllByText('B').length).toBeGreaterThan(0)
})
