/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import NewRecipeModal from '../NewRecipeModal'
import { recipesApi } from '../../api/recipesApi'

vi.mock('../../api/recipesApi', () => ({
  recipesApi: { uploadImage: vi.fn(), fetchAll: vi.fn(() => Promise.resolve([])) },
}))
vi.mock('../../api/tagsApi', () => ({
  tagsApi: { fetchAll: vi.fn(() => Promise.resolve([])) },
}))
vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: { fetchAll: vi.fn(() => Promise.resolve([])) },
}))

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

beforeEach(() => {
  recipesApi.uploadImage.mockReset()
  recipesApi.fetchAll.mockReset()
  recipesApi.fetchAll.mockResolvedValue([
    { id: 7, title: 'Mashed Potatoes', course: 'side' },
    { id: 8, title: 'Steamed Broccoli', course: 'side' },
    { id: 9, title: 'Lasagne', course: 'main' },
  ])
})

const selectCourse = (course) =>
  fireEvent.change(screen.getByLabelText(/course/i), { target: { value: course } })

test('renders a file upload control instead of an image URL text field', () => {
  render(<NewRecipeModal onClose={() => {}} onSave={() => {}} />)
  expect(screen.queryByPlaceholderText('https://…')).toBeNull()
  expect(screen.getByLabelText(/image/i)).toBeInTheDocument()
})

test('uploads a chosen file and sends the returned image_url on save', async () => {
  recipesApi.uploadImage.mockResolvedValue('http://api/recipes/images/recipes/a.png')
  const onSave = vi.fn()
  render(<NewRecipeModal onClose={() => {}} onSave={onSave} />)

  const file = new File(['bytes'], 'a.png', { type: 'image/png' })
  fireEvent.change(screen.getByLabelText(/image/i), { target: { files: [file] } })

  await waitFor(() => expect(recipesApi.uploadImage).toHaveBeenCalledWith(file))
  // Preview thumbnail appears once uploaded.
  await screen.findByAltText(/preview/i)

  fireEvent.submit(screen.getByRole('button', { name: 'Save' }).closest('form'))

  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ image_url: 'http://api/recipes/images/recipes/a.png' })
  )
})

test('favorite sides are curated from the recipe view, not this form', () => {
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={() => {}}
      initialRecipe={{ title: 'Roast', course: 'main', favorite_side_ids: [8] }}
    />
  )

  expect(screen.queryByText(/favorite sides/i)).toBeNull()
  expect(screen.queryByLabelText('Steamed Broccoli')).toBeNull()
})

test('editing a recipe preserves its favorite sides untouched', () => {
  // The form no longer edits them, so it must pass them straight through --
  // otherwise saving a title change would silently wipe the pairings.
  const onSave = vi.fn()
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={onSave}
      initialRecipe={{ title: 'Roast', course: 'main', favorite_side_ids: [7, 8] }}
    />
  )

  fireEvent.change(screen.getByLabelText(/title/i), {
    target: { value: 'Roast Chicken' },
  })
  fireEvent.submit(screen.getByRole('button', { name: 'Save' }).closest('form'))

  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ title: 'Roast Chicken', favorite_side_ids: [7, 8] })
  )
})

test('converting a main into a side drops its favorite sides', () => {
  // The backend rejects a side that carries favorite sides, so passing them
  // through unchanged here would make the save fail with a 400.
  const onSave = vi.fn()
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={onSave}
      initialRecipe={{ title: 'Roast', course: 'main', favorite_side_ids: [7, 8] }}
    />
  )

  selectCourse('side')
  fireEvent.submit(screen.getByRole('button', { name: 'Save' }).closest('form'))

  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ course: 'side', favorite_side_ids: [] })
  )
})

test('a brand-new recipe starts with no favorite sides', () => {
  const onSave = vi.fn()
  render(<NewRecipeModal onClose={() => {}} onSave={onSave} />)
  selectCourse('main')
  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Roast' } })

  fireEvent.submit(screen.getByRole('button', { name: 'Save' }).closest('form'))

  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ favorite_side_ids: [] })
  )
})
