/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import RecipeSort from '../RecipeSort'

afterEach(cleanup)

test('offers every sort option', () => {
  render(<RecipeSort sortKey="default" direction="asc" />)
  const select = screen.getByLabelText('Sort recipes')
  expect([...select.options].map((o) => o.textContent)).toEqual([
    'Default',
    'Score',
    'Name',
    'Type',
  ])
})

test('reports the picked key with its natural direction', () => {
  const onChange = vi.fn()
  render(<RecipeSort sortKey="default" direction="asc" onChange={onChange} />)

  fireEvent.change(screen.getByLabelText('Sort recipes'), { target: { value: 'score' } })

  expect(onChange).toHaveBeenCalledWith('score', 'desc')
})

test('flips the direction when the arrow is pressed', () => {
  const onDirectionChange = vi.fn()
  render(
    <RecipeSort sortKey="name" direction="asc" onDirectionChange={onDirectionChange} />,
  )

  fireEvent.click(screen.getByLabelText('Sort descending'))

  expect(onDirectionChange).toHaveBeenCalledWith('desc')
})

test('the arrow offers the other direction once already descending', () => {
  const onDirectionChange = vi.fn()
  render(
    <RecipeSort sortKey="score" direction="desc" onDirectionChange={onDirectionChange} />,
  )

  fireEvent.click(screen.getByLabelText('Sort ascending'))

  expect(onDirectionChange).toHaveBeenCalledWith('asc')
})

test('direction is meaningless without a sort, so the arrow is disabled', () => {
  render(<RecipeSort sortKey="default" direction="asc" />)
  expect(screen.getByLabelText('Sort descending')).toBeDisabled()
})
