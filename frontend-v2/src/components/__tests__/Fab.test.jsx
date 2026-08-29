/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { PlusIcon } from '@heroicons/react/24/outline'
import Fab from '../Fab'

afterEach(() => cleanup())

test('is reachable by its accessible name and calls onClick', () => {
  const onClick = vi.fn()
  render(<Fab Icon={PlusIcon} label="Add a recipe" onClick={onClick} />)

  fireEvent.click(screen.getByRole('button', { name: 'Add a recipe' }))

  expect(onClick).toHaveBeenCalledTimes(1)
})
