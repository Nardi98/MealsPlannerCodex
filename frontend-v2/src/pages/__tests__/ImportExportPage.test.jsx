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

beforeEach(() => {
  window.alert = vi.fn()
})

/** Pick `data` in the file input, the way a user choosing a backup does. */
async function selectFile(data) {
  const json = JSON.stringify(data)
  const file = new File([json], 'data.json', { type: 'application/json' })
  file.text = () => Promise.resolve(json)
  fireEvent.change(document.querySelector('input[type="file"]'), {
    target: { files: [file] },
  })
  return screen.findByText('Import')
}

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('export button triggers file download', async () => {
  dataApi.exportDatabase.mockResolvedValue({ foo: 'bar' })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:url')
  globalThis.URL.revokeObjectURL = vi.fn()

  render(<ImportExportPage />)
  fireEvent.click(screen.getByRole('button', { name: 'Export Database' }))

  await waitFor(() => expect(dataApi.exportDatabase).toHaveBeenCalled())
  expect(click).toHaveBeenCalled()
})

test('import button appears after file selection', async () => {
  render(<ImportExportPage />)
  expect(screen.queryByText('Import')).toBeNull()

  const btn = await selectFile({})
  expect(btn).toBeEnabled()
})

test('merge conflict modal opens when conflicts detected', async () => {
  const data = {
    recipes: [{ title: 'Recipe A', ingredients: [{ name: 'Salt' }] }],
  }
  recipesApi.fetchAll.mockResolvedValue([{ id: 1, title: 'Recipe A' }])

  render(<ImportExportPage />)

  await selectFile(data)
  const btn = await screen.findByText('Import')
  fireEvent.click(btn)

  await screen.findByText('Resolve Conflicts')
  expect(dataApi.importDatabase).not.toHaveBeenCalled()
})

test('overwrite confirmation modal shown in overwrite mode', async () => {
  render(<ImportExportPage />)
  const select = document.querySelector('select')
  fireEvent.change(select, { target: { value: 'overwrite' } })

  const btn = await selectFile({})
  fireEvent.click(btn)

  await screen.findByText('Overwrite Existing Data')
  expect(dataApi.importDatabase).not.toHaveBeenCalled()
})


// Selecting a file, hitting Import, and resolving the conflict must still send
// the file that was chosen. The conflict path used to clear the parsed payload
// on its way to the modal, so confirming imported an empty object and the user
// was told the import had succeeded.
test('resolving a conflict imports the payload that was chosen', async () => {
  const data = {
    recipes: [
      { id: 1, title: 'Recipe A', ingredients: [{ name: 'Salt' }] },
      { id: 2, title: 'Recipe B', ingredients: [{ name: 'Pepper' }] },
    ],
    tags: [{ id: 5, name: 'summer' }],
  }
  recipesApi.fetchAll.mockResolvedValue([{ id: 9, title: 'Recipe A' }])
  dataApi.importDatabase.mockResolvedValue({ status: 'ok' })

  render(<ImportExportPage />)
  fireEvent.click(await selectFile(data))

  await screen.findByText('Resolve Conflicts')
  fireEvent.click(screen.getByLabelText('keep both'))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

  await waitFor(() => expect(dataApi.importDatabase).toHaveBeenCalled())
  const [payload, mode] = dataApi.importDatabase.mock.calls[0]
  expect(mode).toBe('merge')
  expect(payload.recipes.map((r) => r.title)).toEqual(['Recipe A', 'Recipe B'])
  expect(payload.tags).toHaveLength(1)
})

// Ingredients are a shared pantry: the backend already reuses an existing one
// by name rather than duplicating it, so an overlapping name is the normal
// case and not something to interrupt the user about.
test('shared ingredient names are not conflicts', async () => {
  const data = {
    recipes: [{ id: 1, title: 'Brand New Recipe', ingredients: [{ name: 'Salt' }] }],
  }
  recipesApi.fetchAll.mockResolvedValue([{ id: 9, title: 'Something Else' }])
  dataApi.importDatabase.mockResolvedValue({ status: 'ok' })

  render(<ImportExportPage />)
  fireEvent.click(await selectFile(data))

  await waitFor(() => expect(dataApi.importDatabase).toHaveBeenCalledWith(data, 'merge'))
  expect(screen.queryByText('Resolve Conflicts')).toBeNull()
})

// "Import successful" over an empty import is what hid the bug above, so the
// message says what actually landed.
test('the success message reports what was imported', async () => {
  const data = { recipes: [{ id: 1, title: 'Recipe A', ingredients: [] }] }
  recipesApi.fetchAll.mockResolvedValue([])
  dataApi.importDatabase.mockResolvedValue({
    status: 'ok',
    imported: { recipes: 1, ingredients: 3, tags: 2, meal_plans: 0 },
  })

  render(<ImportExportPage />)
  fireEvent.click(await selectFile(data))

  await waitFor(() => expect(window.alert).toHaveBeenCalled())
  const message = window.alert.mock.calls[0][0]
  expect(message).toMatch(/1 recipe/)
  expect(message).toMatch(/3 ingredients/)
  expect(message).toMatch(/2 tags/)
})
