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
  recipesApi: { uploadImage: vi.fn() },
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
})

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
