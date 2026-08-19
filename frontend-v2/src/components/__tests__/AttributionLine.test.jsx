/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import AttributionLine, { AttributionLine as Named } from '../AttributionLine'

afterEach(cleanup)

// The contract below is frozen: RecipesPage places this component against it.
// Named + default export, prop `recipe`, null when there is no source author.

test('exports the same component as both a named and a default export', () => {
  expect(Named).toBe(AttributionLine)
})

test('renders nothing when the recipe was not copied from anyone', () => {
  const { container } = render(<AttributionLine recipe={{ id: 1, title: 'Mine' }} />)

  expect(container).toBeEmptyDOMElement()
})

test('renders nothing when there is no recipe at all', () => {
  const { container } = render(<AttributionLine recipe={undefined} />)

  expect(container).toBeEmptyDOMElement()
})

test('credits the snapshotted source title and author handle (AT-3)', () => {
  render(
    <AttributionLine
      recipe={{ source_author_username: 'anna', source_recipe_title: 'Ribollita' }}
    />
  )

  expect(screen.getByText('Adapted from Ribollita by @anna')).toBeInTheDocument()
})

test('offers no control that removes or hides the credit (AT-4 / AT-5)', () => {
  const { container } = render(
    <AttributionLine
      recipe={{ source_author_username: 'anna', source_recipe_title: 'Ribollita' }}
    />
  )

  expect(container.querySelectorAll('button, a, input, [role="button"]')).toHaveLength(0)
})

test('escapes author-controlled text rather than rendering it as markup', () => {
  const { container } = render(
    <AttributionLine
      recipe={{
        source_author_username: 'anna',
        source_recipe_title: '<img src=x onerror="alert(1)">',
      }}
    />
  )

  expect(container.querySelector('img')).toBeNull()
  expect(container.textContent).toContain('<img src=x onerror="alert(1)">')
})

test('renders the credit even when the copy has been renamed beyond recognition', () => {
  // AT-5: no divergence or edit-distance threshold weakens attribution.
  render(
    <AttributionLine
      recipe={{
        title: 'Completely Different Soup',
        procedure: 'Nothing like the original.',
        source_author_username: 'anna',
        source_recipe_title: 'Ribollita',
      }}
    />
  )

  expect(screen.getByText(/Adapted from Ribollita by @anna/)).toBeInTheDocument()
})
