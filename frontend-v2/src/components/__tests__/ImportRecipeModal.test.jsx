/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ImportRecipeModal from '../ImportRecipeModal'
import { recipesApi } from '../../api/recipesApi'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    create: vi.fn(),
    uploadImage: vi.fn(),
    fetchAll: vi.fn(() => Promise.resolve([])),
  },
}))
vi.mock('../../api/tagsApi', () => ({
  tagsApi: { fetchAll: vi.fn(() => Promise.resolve([])) },
}))
vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: { fetchAll: vi.fn(), create: vi.fn(), similar: vi.fn() },
}))

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

beforeEach(() => {
  ingredientsApi.fetchAll.mockReset()
  ingredientsApi.create.mockReset()
  ingredientsApi.similar.mockReset()
  ingredientsApi.similar.mockResolvedValue([])
  recipesApi.create.mockReset()
  recipesApi.fetchAll.mockResolvedValue([])
  // One existing ingredient ("Basil") to match against; "Pasta" is new.
  ingredientsApi.fetchAll.mockResolvedValue([
    { id: 3, name: 'Basil', unit: 'g', season_months: [5, 6] },
  ])
})

const payload = JSON.stringify({
  title: 'Pasta al Pesto',
  course: 'main',
  procedure: 'Mix.',
  tags: ['quick'],
  ingredients: [
    { name: 'Basil', quantity: 50, unit: 'g' },
    { name: 'Pasta', quantity: 100, unit: 'g' },
  ],
})

const pasteAndContinue = (raw) => {
  fireEvent.change(screen.getByLabelText(/paste/i), { target: { value: raw } })
  fireEvent.click(screen.getByRole('button', { name: /continue/i }))
}

test('shows the chatbot prompt and a copy button', () => {
  render(<ImportRecipeModal onClose={() => {}} onCreated={() => {}} />)
  expect(screen.getByRole('button', { name: /copy prompt/i })).toBeInTheDocument()
  expect(screen.getByText(/single serving/i)).toBeInTheDocument()
})

test('shows an error for invalid pasted JSON and stays on the prompt step', () => {
  render(<ImportRecipeModal onClose={() => {}} onCreated={() => {}} />)
  pasteAndContinue('{ not json')
  expect(screen.getByText(/valid json/i)).toBeInTheDocument()
})

test('valid JSON reveals reconciliation: matched ingredient linked, new one needs a unit', async () => {
  render(<ImportRecipeModal onClose={() => {}} onCreated={() => {}} />)
  pasteAndContinue(payload)

  // Matched existing ingredient is shown as linked.
  await screen.findByText(/matches existing/i)
  // The new ingredient ("Pasta") exposes a unit selector for creation.
  expect(screen.getByLabelText(/pasta unit/i)).toBeInTheDocument()
})

test('confirming creates new ingredients then opens the pre-filled editor', async () => {
  ingredientsApi.create.mockResolvedValue({ id: 9, name: 'Pasta', unit: 'g' })
  render(<ImportRecipeModal onClose={() => {}} onCreated={() => {}} />)
  pasteAndContinue(payload)

  await screen.findByText(/matches existing/i)
  fireEvent.click(screen.getByRole('button', { name: /confirm ingredients/i }))

  await waitFor(() =>
    expect(ingredientsApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Pasta' })
    )
  )
  // Editor opens pre-filled with the imported title.
  await waitFor(() =>
    expect(screen.getByLabelText(/title/i)).toHaveValue('Pasta al Pesto')
  )
})

test('suggests a similar existing ingredient and links it instead of creating one', async () => {
  // "Pasta" has no exact match but is similar to the existing "Pastina".
  ingredientsApi.fetchAll.mockResolvedValue([
    { id: 3, name: 'Basil', unit: 'g', season_months: [5, 6] },
    { id: 5, name: 'Pastina', unit: 'g', season_months: [] },
  ])
  ingredientsApi.similar.mockImplementation((name) =>
    Promise.resolve(
      name === 'Pasta' ? [{ id: 5, name: 'Pastina', unit: 'g' }] : []
    )
  )
  render(<ImportRecipeModal onClose={() => {}} onCreated={() => {}} />)
  pasteAndContinue(payload)

  await screen.findByText(/matches existing/i)
  // Switch the new "Pasta" row (2nd row) to "Use existing".
  const useExisting = screen.getAllByRole('radio', { name: /use existing/i })
  fireEvent.click(useExisting[1])

  // The similar ingredient is suggested; pick it.
  fireEvent.click(await screen.findByRole('button', { name: /pastina/i }))
  fireEvent.click(screen.getByRole('button', { name: /confirm ingredients/i }))

  // Linked to the existing ingredient, so nothing new is created.
  await screen.findByLabelText(/title/i)
  expect(ingredientsApi.create).not.toHaveBeenCalled()
})

test('saving from the editor creates the recipe and reports it', async () => {
  ingredientsApi.create.mockResolvedValue({ id: 9, name: 'Pasta', unit: 'g' })
  recipesApi.create.mockResolvedValue({ id: 42, title: 'Pasta al Pesto' })
  const onCreated = vi.fn()
  render(<ImportRecipeModal onClose={() => {}} onCreated={onCreated} />)
  pasteAndContinue(payload)

  await screen.findByText(/matches existing/i)
  fireEvent.click(screen.getByRole('button', { name: /confirm ingredients/i }))
  await screen.findByLabelText(/title/i)

  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(recipesApi.create).toHaveBeenCalled())
  await waitFor(() =>
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 42 }))
  )
})
