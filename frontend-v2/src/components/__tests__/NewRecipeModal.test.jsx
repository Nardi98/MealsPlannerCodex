/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import NewRecipeModal from '../NewRecipeModal'
import { recipesApi } from '../../api/recipesApi'
import { ingredientsApi } from '../../api/ingredientsApi'
import { tagsApi } from '../../api/tagsApi'

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


// --- servings basis ---------------------------------------------------------

test('saves a new recipe as written for one person by default', async () => {
  const onSave = vi.fn()
  render(<NewRecipeModal onClose={() => {}} onSave={onSave} />)

  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Toast' } })
  selectCourse('main')
  fireEvent.click(screen.getByRole('button', { name: /save/i }))

  await waitFor(() => expect(onSave).toHaveBeenCalled())
  expect(onSave.mock.calls[0][0].servings).toBe(1)
})

test('saves the servings basis the cook typed', async () => {
  const onSave = vi.fn()
  render(<NewRecipeModal onClose={() => {}} onSave={onSave} />)

  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Ribollita' } })
  selectCourse('main')
  fireEvent.change(screen.getByLabelText(/serves/i), { target: { value: '4' } })
  fireEvent.click(screen.getByRole('button', { name: /save/i }))

  await waitFor(() => expect(onSave).toHaveBeenCalled())
  expect(onSave.mock.calls[0][0].servings).toBe(4)
})

test('tells the cook which head-count the quantities are for', () => {
  render(<NewRecipeModal onClose={() => {}} onSave={() => {}} />)

  fireEvent.change(screen.getByLabelText(/serves/i), { target: { value: '4' } })

  expect(screen.getByText(/quantities for 4 people/i)).toBeInTheDocument()
})

test('changing the servings basis never rewrites the typed quantities', async () => {
  const onSave = vi.fn()
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={onSave}
      initialRecipe={{
        title: 'Ribollita',
        course: 'main',
        servings: 4,
        ingredients: [{ id: 1, name: 'Cavolo nero', amount: 800, unit: 'g' }],
      }}
    />,
  )

  expect(screen.getByLabelText(/serves/i)).toHaveValue(4)
  fireEvent.change(screen.getByLabelText(/serves/i), { target: { value: '8' } })
  fireEvent.click(screen.getByRole('button', { name: /save/i }))

  await waitFor(() => expect(onSave).toHaveBeenCalled())
  const saved = onSave.mock.calls[0][0]
  expect(saved.servings).toBe(8)
  expect(saved.ingredients[0].amount).toBe(800)
})

// An import hands this modal ingredient lines that learned physical facts from
// the chatbot. The recipe save is what carries them to the server, so dropping
// them here would silently stop imports teaching the pantry anything.
test('saving keeps the conversions an imported line arrived with', async () => {
  const onSave = vi.fn()
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={onSave}
      initialRecipe={{
        title: 'Soffritto',
        course: 'main',
        ingredients: [
          {
            id: 4,
            name: 'Onion',
            amount: 2,
            unit: 'piece',
            grams_per_piece: 150,
            grams_per_ml: null,
          },
        ],
      }}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: /save/i }))

  await waitFor(() => expect(onSave).toHaveBeenCalled())
  expect(onSave.mock.calls[0][0].ingredients[0]).toMatchObject({
    grams_per_piece: 150,
  })
})

// --- Injectable sources (catalog mode, plan D3) -----------------------------

// Opens the first ingredient row's dropdown.
const openIngredientDropdown = () => fireEvent.focus(screen.getByPlaceholderText('ingredient'))

test('by default it loads the user pantry and tags and offers to add an ingredient', async () => {
  ingredientsApi.fetchAll.mockResolvedValue([{ id: 1, name: 'Basil', unit: 'g' }])
  tagsApi.fetchAll.mockResolvedValue([{ id: 2, name: 'quick' }])
  render(<NewRecipeModal onClose={() => {}} onSave={() => {}} />)

  await waitFor(() => expect(ingredientsApi.fetchAll).toHaveBeenCalled())
  expect(tagsApi.fetchAll).toHaveBeenCalled()
  expect(screen.getByRole('heading', { name: 'New Recipe' })).toBeInTheDocument()
  openIngredientDropdown()
  expect(await screen.findByText('Basil')).toBeInTheDocument()
  expect(screen.getByText('+ Add new ingredient')).toBeInTheDocument()
})

test('loadIngredients and loadTags replace the user sources when passed', async () => {
  const loadIngredients = vi.fn(() => Promise.resolve([{ id: 50, name: 'Cavolo nero' }]))
  const loadTags = vi.fn(() => Promise.resolve([{ id: 60, name: 'soup' }]))
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={() => {}}
      loadIngredients={loadIngredients}
      loadTags={loadTags}
    />,
  )

  await waitFor(() => expect(loadIngredients).toHaveBeenCalled())
  expect(loadTags).toHaveBeenCalled()
  expect(ingredientsApi.fetchAll).not.toHaveBeenCalled()
  expect(tagsApi.fetchAll).not.toHaveBeenCalled()
  openIngredientDropdown()
  expect(await screen.findByText('Cavolo nero')).toBeInTheDocument()
  fireEvent.focus(screen.getByPlaceholderText('tag'))
  expect(await screen.findByText('soup')).toBeInTheDocument()
})

test('allowCreateIngredient={false} removes the add-ingredient control', async () => {
  const loadIngredients = vi.fn(() => Promise.resolve([{ id: 50, name: 'Cavolo nero' }]))
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={() => {}}
      loadIngredients={loadIngredients}
      allowCreateIngredient={false}
    />,
  )

  openIngredientDropdown()
  expect(await screen.findByText('Cavolo nero')).toBeInTheDocument()
  expect(screen.queryByText(/add new ingredient/i)).toBeNull()
})

test('allowImageUpload={false} hides the upload control but keeps an existing image', async () => {
  const onSave = vi.fn()
  render(
    <NewRecipeModal
      onClose={() => {}}
      onSave={onSave}
      allowImageUpload={false}
      initialRecipe={{ title: 'Roast', course: 'main', image_url: 'http://img/a.png' }}
    />,
  )

  expect(screen.queryByLabelText(/image/i)).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: /save/i }))
  await waitFor(() => expect(onSave).toHaveBeenCalled())
  expect(onSave.mock.calls[0][0].image_url).toBe('http://img/a.png')
})

test('heading replaces the form title', () => {
  render(<NewRecipeModal onClose={() => {}} onSave={() => {}} heading="New catalog recipe" />)
  expect(screen.getByRole('heading', { name: 'New catalog recipe' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'New Recipe' })).toBeNull()
})

test('save hands the recipe over and closes without waiting on onSave', () => {
  // The page owns error feedback for a failed save: the form is already gone.
  const order = []
  const onSave = vi.fn(() => {
    order.push('save')
    return new Promise(() => {})
  })
  const onClose = vi.fn(() => order.push('close'))
  render(<NewRecipeModal onClose={onClose} onSave={onSave} initialRecipe={{ title: 'Roast', course: 'main' }} />)

  fireEvent.click(screen.getByRole('button', { name: /save/i }))

  expect(order).toEqual(['save', 'close'])
})
