/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useOnClickOutside } from '../useOnClickOutside'

afterEach(cleanup)

function Harness({ active, onOutside }) {
  const ref = React.useRef(null)
  useOnClickOutside(ref, active, onOutside)
  return (
    <div>
      <div data-testid="inside" ref={ref}>
        <span data-testid="nested">nested</span>
      </div>
      <div data-testid="outside">outside</div>
    </div>
  )
}

test('calls back on a mousedown outside the element', () => {
  const onOutside = vi.fn()
  const { getByTestId } = render(<Harness active onOutside={onOutside} />)

  fireEvent.mouseDown(getByTestId('outside'))

  expect(onOutside).toHaveBeenCalledTimes(1)
})

test('ignores a mousedown on the element or anything inside it', () => {
  const onOutside = vi.fn()
  const { getByTestId } = render(<Harness active onOutside={onOutside} />)

  fireEvent.mouseDown(getByTestId('inside'))
  fireEvent.mouseDown(getByTestId('nested'))

  expect(onOutside).not.toHaveBeenCalled()
})

test('does nothing while inactive', () => {
  const onOutside = vi.fn()
  const { getByTestId } = render(<Harness active={false} onOutside={onOutside} />)

  fireEvent.mouseDown(getByTestId('outside'))

  expect(onOutside).not.toHaveBeenCalled()
})

test('stops listening on unmount', () => {
  const onOutside = vi.fn()
  const { unmount } = render(<Harness active onOutside={onOutside} />)

  unmount()
  fireEvent.mouseDown(document.body)

  expect(onOutside).not.toHaveBeenCalled()
})
