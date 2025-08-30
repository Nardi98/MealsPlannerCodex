import React, { useState } from 'react'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
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
    if (url.endsWith('/feedback/accept')) {
       return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'A', sides: [] }] })
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

  renderWithPlan({ '2024-01-01': [{ main: 'A', sides: [] }, { main: 'C', sides: [] }] })
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
    '2024-01-01': [{ main: 'A', sides: [] }],
    '2024-01-03': [{ main: 'A (leftover)', sides: [] }],
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

test('add side dish persists via API', async () => {
  let sidePayload = null
  global.fetch = vi.fn((url, opts) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve([
            { id: 1, title: 'Main', course: 'main' },
            { id: 2, title: 'Side', course: 'side' },
          ]),
      })
    }
    if (url.endsWith('/meal-plans/side')) {
      sidePayload = JSON.parse(opts.body)
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'Main', sides: [] }] })
  const btn = await screen.findByText('Add Side Dish')
  fireEvent.click(btn)
  const dialog = await screen.findByText('Choose Side Dish')
  const list = dialog.parentElement.querySelector('ul')
  expect(within(list).queryByText('Main')).toBeNull()
  fireEvent.click(within(list).getByText('Side'))
  const cell = screen.getByText('Main').closest('td')
  await within(cell).findByText('Side', { exact: true })
  expect(sidePayload).toEqual({ plan_date: '2024-01-01', meal_number: 1, side_id: 2, index: 0 })
})

test('generate side dish persists via API', async () => {
  let sidePayload = null
  let generatePayload = null
  global.fetch = vi.fn((url, opts) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve([
            { id: 1, title: 'Main', course: 'main' },
            { id: 2, title: 'Other', course: 'side' },
          ]),
      })
    }
    if (url.endsWith('/side-dishes/generate')) {
      generatePayload = JSON.parse(opts.body)
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: 3, title: 'Generated' }),
      })
    }
    if (url.endsWith('/meal-plans/side')) {
      sidePayload = JSON.parse(opts.body)
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'Main', sides: [] }] })
  fireEvent.click(screen.getByText('Show Settings'))
  await screen.findByText('Advanced Options')
  fireEvent.change(screen.getByLabelText('ε'), { target: { value: '0.2' } })
  fireEvent.change(screen.getByLabelText('Keep Days'), { target: { value: '5' } })
  fireEvent.change(screen.getByLabelText('Avoid Tags'), { target: { value: 'a, b' } })
  fireEvent.change(screen.getByLabelText('Reduce Tags'), { target: { value: 'c' } })
  const addBtn = await screen.findByText('Add Side Dish')
  fireEvent.click(addBtn)
  const genBtn = await screen.findByText('Generate Side')
  fireEvent.click(genBtn)
  const cell = screen.getByText('Main').closest('td')
  await within(cell).findByText('Generated', { exact: false })
  expect(generatePayload).toEqual({
    epsilon: 0.2,
    avoid_tags: ['a', 'b'],
    reduce_tags: ['c'],
    keep_days: 5,
  })
  expect(sidePayload).toEqual({ plan_date: '2024-01-01', meal_number: 1, side_id: 3, index: 0 })
})

test('add multiple side dishes uses correct indexes', async () => {
  const sideCalls = []
  global.fetch = vi.fn((url, opts) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve([
            { id: 1, title: 'Main', course: 'main' },
            { id: 2, title: 'Side1', course: 'side' },
            { id: 3, title: 'Side2', course: 'side' },
          ]),
      })
    }
    if (url.endsWith('/meal-plans/side')) {
      sideCalls.push(JSON.parse(opts.body))
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'Main', sides: [] }] })
  const first = await screen.findByText('Add Side Dish')
  fireEvent.click(first)
  let dialog = await screen.findByText('Choose Side Dish')
  let list = dialog.parentElement.querySelector('ul')
  fireEvent.click(within(list).getByText('Side1'))
  const cell = screen.getByText('Main').closest('td')
  await within(cell).findByText('Side1', { exact: true })

  const second = screen.getByText('Add Side Dish')
  fireEvent.click(second)
  dialog = await screen.findByText('Choose Side Dish')
  list = dialog.parentElement.querySelector('ul')
  fireEvent.click(within(list).getByText('Side2'))
  await within(cell).findByText('Side2', { exact: true })

  expect(sideCalls).toEqual([
    { plan_date: '2024-01-01', meal_number: 1, side_id: 2, index: 0 },
    { plan_date: '2024-01-01', meal_number: 1, side_id: 3, index: 1 },
  ])
})

test('swap side dish persists via API with correct index', async () => {
  let sidePayload = null
  global.fetch = vi.fn((url, opts) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve([
            { id: 1, title: 'Main', course: 'main' },
            { id: 2, title: 'Side1', course: 'side' },
            { id: 3, title: 'Side2', course: 'side' },
            { id: 4, title: 'Side3', course: 'side' },
          ]),
      })
    }
    if (url.endsWith('/meal-plans/side')) {
      if (opts.method === 'POST') sidePayload = JSON.parse(opts.body)
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'Main', sides: ['Side1', 'Side2'] }] })
  const cell = screen.getByText('Main').closest('td')
  const side2 = within(cell).getAllByText('Side2')[0].closest('div')
  fireEvent.click(within(side2).getByText('Swap'))
  const dialog = await screen.findByText('Choose Side Dish')
  const list = dialog.parentElement.querySelector('ul')
  fireEvent.click(within(list).getByText('Side3'))
  await within(cell).findByText('Side3', { exact: true })
  expect(within(cell).getAllByText('Side1').length).toBe(1)
  expect(sidePayload).toEqual({ plan_date: '2024-01-01', meal_number: 1, side_id: 4, index: 1 })
})

test('remove side dish persists via API with correct index', async () => {
  let removePayload = null
  global.fetch = vi.fn((url, opts) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/meal-plans/side')) {
      if (opts.method === 'DELETE') removePayload = JSON.parse(opts.body)
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'Main', sides: ['Side1', 'Side2'] }] })
  const cell = screen.getByText('Main').closest('td')
  const side2 = within(cell).getAllByText('Side2')[0].closest('div')
  fireEvent.click(within(side2).getByText('Remove'))
  await waitFor(() => expect(within(cell).queryByText('Side2')).toBeNull())
  expect(removePayload).toEqual({ plan_date: '2024-01-01', meal_number: 1, index: 1 })
})

test('settings panel toggles and updates inputs', async () => {
  global.fetch = vi.fn((url) => {
    if (url.endsWith('/plan/settings')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ keep_days: 1 }) })
    }
    if (url.endsWith('/recipes')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })

  renderWithPlan({ '2024-01-01': [{ main: 'A', sides: [] }] })
  expect(screen.queryByText('Advanced Options')).toBeNull()
  fireEvent.click(screen.getByText('Show Settings'))
  await screen.findByText('Advanced Options')
  const eps = screen.getByLabelText('ε')
  fireEvent.change(eps, { target: { value: '0.5' } })
  expect(eps.value).toBe('0.5')
  const keep = screen.getByLabelText('Keep Days')
  fireEvent.change(keep, { target: { value: '5' } })
  expect(keep.value).toBe('5')
  fireEvent.click(screen.getByText('Hide Settings'))
  await waitFor(() => expect(screen.queryByText('Advanced Options')).toBeNull())
})
