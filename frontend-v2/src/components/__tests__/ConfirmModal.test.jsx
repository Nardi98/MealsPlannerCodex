/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ConfirmModal from '../ConfirmModal'

afterEach(() => cleanup())

const props = {
  title: 'Delete Risotto?',
  message: "This can't be undone.",
  confirmLabel: 'Delete',
}

test('confirming calls onConfirm', () => {
  const onConfirm = vi.fn()
  render(<ConfirmModal {...props} onConfirm={onConfirm} onCancel={() => {}} />)

  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

  expect(onConfirm).toHaveBeenCalledTimes(1)
})

test('cancelling calls onCancel and never onConfirm', () => {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(<ConfirmModal {...props} onConfirm={onConfirm} onCancel={onCancel} />)

  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

  expect(onCancel).toHaveBeenCalledTimes(1)
  expect(onConfirm).not.toHaveBeenCalled()
})

test('Escape cancels', () => {
  const onCancel = vi.fn()
  render(<ConfirmModal {...props} onConfirm={() => {}} onCancel={onCancel} />)

  fireEvent.keyDown(document, { key: 'Escape' })

  expect(onCancel).toHaveBeenCalledTimes(1)
})

// Cancel is the safe default and comes first in the tab order, so it is also
// what a keyboard lands on when the gate opens.
test('takes focus on open and gives it back on close', () => {
  const opener = document.createElement('button')
  document.body.appendChild(opener)
  opener.focus()

  const { unmount } = render(
    <ConfirmModal {...props} onConfirm={() => {}} onCancel={() => {}} />,
  )
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }))

  unmount()

  expect(document.activeElement).toBe(opener)
  opener.remove()
})

test('Tab does not escape into the dialog it was raised from', () => {
  render(<ConfirmModal {...props} onConfirm={() => {}} onCancel={() => {}} />)
  screen.getByRole('button', { name: 'Delete' }).focus()

  fireEvent.keyDown(document, { key: 'Tab' })

  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }))
})
