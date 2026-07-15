/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import Avatar from '../Avatar'

afterEach(cleanup)

test('renders two-letter initials from a display name', () => {
  render(<Avatar name="Alessandro Nardi" />)
  expect(screen.getByText('AN')).toBeInTheDocument()
})

test('renders a single initial from a one-word name', () => {
  render(<Avatar name="Demo" />)
  expect(screen.getByText('D')).toBeInTheDocument()
})

test('falls back to the email initial when no name is given', () => {
  render(<Avatar email="demo@mealplanner.test" />)
  expect(screen.getByText('D')).toBeInTheDocument()
})

test('uses a placeholder when neither name nor email is given', () => {
  render(<Avatar />)
  expect(screen.getByText('?')).toBeInTheDocument()
})

test('derives a deterministic background color from the identity', () => {
  const { container: a } = render(<Avatar name="Alessandro Nardi" />)
  const first = a.firstChild.style.background
  cleanup()
  const { container: b } = render(<Avatar name="Alessandro Nardi" />)
  expect(b.firstChild.style.background).toBe(first)
  expect(first).not.toBe('')
})
