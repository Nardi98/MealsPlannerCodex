/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import SystemIngredientForm from '../catalog/SystemIngredientForm'
import { stubViewport } from '../../test/stubViewport'

stubViewport(false)

afterEach(cleanup)

const CHESTNUT = {
  id: 7,
  name: 'Chestnut',
  season_months: [10, 11],
  categories: ['Fruit'],
  grams_per_ml: null,
  grams_per_piece: 8,
  preferred_dimension: 'piece',
}

const type = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } })
const save = () => fireEvent.click(screen.getByRole('button', { name: 'Save ingredient' }))

test('creating sends the whole ingredient, with the untouched fields empty', () => {
  const onSubmit = vi.fn()
  render(<SystemIngredientForm submitLabel="Save ingredient" onSubmit={onSubmit} />)

  type('Name', 'Chestnut')
  type('Grams per piece', '8')
  type('Measured in', 'piece')
  save()

  expect(onSubmit).toHaveBeenCalledWith({
    name: 'Chestnut',
    season_months: [],
    categories: [],
    grams_per_ml: null,
    grams_per_piece: 8,
    preferred_dimension: 'piece',
  })
})

test('editing sends only the field that changed, so the rest are left alone', () => {
  const onSubmit = vi.fn()
  render(<SystemIngredientForm ingredient={CHESTNUT} submitLabel="Save ingredient" onSubmit={onSubmit} />)

  expect(screen.getByLabelText('Name')).toHaveValue('Chestnut')
  expect(screen.getByLabelText('Grams per piece')).toHaveValue(8)

  type('Name', 'Sweet chestnut')
  save()

  expect(onSubmit).toHaveBeenCalledWith({ name: 'Sweet chestnut' })
})

test('emptying a number sends an explicit null, which is how a wrong value is cleared', () => {
  const onSubmit = vi.fn()
  render(<SystemIngredientForm ingredient={CHESTNUT} submitLabel="Save ingredient" onSubmit={onSubmit} />)

  type('Grams per piece', '')
  save()

  expect(onSubmit).toHaveBeenCalledWith({ grams_per_piece: null })
})

test('a blank name is refused here rather than costing a request', () => {
  const onSubmit = vi.fn()
  render(<SystemIngredientForm submitLabel="Save ingredient" onSubmit={onSubmit} />)

  type('Name', '   ')
  save()

  expect(onSubmit).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('needs a name')
})

test('the caller’s error is shown, and Cancel only appears when there is somewhere to go', () => {
  const onCancel = vi.fn()
  const { rerender } = render(
    <SystemIngredientForm submitLabel="Save ingredient" error="Chestnut already exists." onSubmit={vi.fn()} />
  )

  expect(screen.getByRole('alert')).toHaveTextContent('Chestnut already exists.')
  expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull()

  rerender(<SystemIngredientForm submitLabel="Save ingredient" onSubmit={vi.fn()} onCancel={onCancel} />)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(onCancel).toHaveBeenCalled()
})

test('the months and categories controls write their arrays into the payload', () => {
  const onSubmit = vi.fn()
  render(<SystemIngredientForm submitLabel="Save ingredient" onSubmit={onSubmit} />)

  type('Name', 'Kale')
  fireEvent.click(screen.getByRole('button', { name: 'Select months' }))
  fireEvent.click(screen.getByRole('button', { name: 'Jan' }))
  fireEvent.click(screen.getByRole('button', { name: 'Vegetables' }))
  save()

  expect(onSubmit).toHaveBeenCalledWith(
    expect.objectContaining({ name: 'Kale', season_months: [1], categories: ['Vegetables'] })
  )
})
