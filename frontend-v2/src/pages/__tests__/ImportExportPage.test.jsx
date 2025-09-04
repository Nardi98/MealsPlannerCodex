/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ImportExportPage from '../ImportExportPage'
import { dataApi } from '../../api/dataApi'
import { recipesApi } from '../../api/recipesApi'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/dataApi', () => ({
  dataApi: {
    exportDatabase: vi.fn(),
    importDatabase: vi.fn(),
  },
}))

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
  },
}))

vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: {
    fetchAll: vi.fn(),
  },
}))

beforeEach(() => {
  window.alert = vi.fn()
})

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('export button triggers file download', async () => {
  dataApi.exportDatabase.mockResolvedValue({ foo: 'bar' })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  global.URL.createObjectURL = vi.fn(() => 'blob:url')
  global.URL.revokeObjectURL = vi.fn()

  render(<ImportExportPage />)
  fireEvent.click(screen.getByRole('button', { name: 'Export Database' }))

  await waitFor(() => expect(dataApi.exportDatabase).toHaveBeenCalled())
  expect(click).toHaveBeenCalled()
})

test('import button appears after file selection', async () => {
  render(<ImportExportPage />)
  expect(screen.queryByText('Import')).toBeNull()

  const file = new File([JSON.stringify({})], 'data.json', {
    type: 'application/json',
  })
  file.text = () => Promise.resolve(JSON.stringify({}))
  const input = document.querySelector('input[type="file"]')
  fireEvent.change(input, { target: { files: [file] } })

  const btn = await screen.findByText('Import')
  expect(btn).toBeEnabled()
})

test('merge conflict modal opens when conflicts detected', async () => {
  const data = {
    recipes: [{ title: 'Recipe A', ingredients: [{ name: 'Salt' }] }],
  }
  recipesApi.fetchAll.mockResolvedValue([{ id: 1, title: 'Recipe A' }])
  ingredientsApi.fetchAll.mockResolvedValue([{ id: 1, name: 'Salt' }])

  render(<ImportExportPage />)

  const file = new File([JSON.stringify(data)], 'data.json', {
    type: 'application/json',
  })
  file.text = () => Promise.resolve(JSON.stringify(data))
  const input = document.querySelector('input[type="file"]')
  fireEvent.change(input, { target: { files: [file] } })
  const btn = await screen.findByText('Import')
  fireEvent.click(btn)

  await screen.findByText('Resolve Conflicts')
  expect(dataApi.importDatabase).not.toHaveBeenCalled()
})

test('overwrite confirmation modal shown in overwrite mode', async () => {
  render(<ImportExportPage />)
  const select = document.querySelector('select')
  fireEvent.change(select, { target: { value: 'overwrite' } })

  const file = new File([JSON.stringify({})], 'data.json', {
    type: 'application/json',
  })
  file.text = () => Promise.resolve(JSON.stringify({}))
  const input = document.querySelector('input[type="file"]')
  fireEvent.change(input, { target: { files: [file] } })
  const btn = await screen.findByText('Import')
  fireEvent.click(btn)

  await screen.findByText('Overwrite Existing Data')
  expect(dataApi.importDatabase).not.toHaveBeenCalled()
})

