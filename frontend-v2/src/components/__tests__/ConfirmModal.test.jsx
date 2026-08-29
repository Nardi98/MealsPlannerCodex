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
