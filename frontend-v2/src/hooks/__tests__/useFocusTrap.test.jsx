/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, cleanup, screen, fireEvent, createEvent } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { useFocusTrap } from '../useFocusTrap'

afterEach(() => cleanup())

// A dialog-shaped consumer: the hook takes a ref to the element that bounds
// the trap, exactly as BottomSheet and ModalScrim will pass it.
function Trapped({ active = true, children }) {
  const ref = React.useRef(null)
  useFocusTrap(active, ref)
  return <div ref={ref}>{children}</div>
}

test('focuses the first focusable element inside the container', () => {
  render(
    <Trapped>
      <button type="button">first</button>
      <button type="button">second</button>
    </Trapped>,
  )

  expect(document.activeElement).toHaveTextContent('first')
})

test('focuses the container itself when it holds nothing focusable', () => {
  const { container } = render(
    <Trapped>
      <p>nothing to focus</p>
    </Trapped>,
  )

  expect(document.activeElement).toBe(container.firstChild)
})

test('restores focus to whatever was focused before it opened', () => {
  const opener = document.createElement('button')
  opener.textContent = 'opener'
  document.body.appendChild(opener)
  opener.focus()

  const { unmount } = render(
    <Trapped>
      <button type="button">inside</button>
    </Trapped>,
  )
  expect(document.activeElement).toHaveTextContent('inside')

  unmount()

  expect(document.activeElement).toBe(opener)
  opener.remove()
})

test('does nothing at all while inactive', () => {
  const opener = document.createElement('button')
  document.body.appendChild(opener)
  opener.focus()

  render(
    <Trapped active={false}>
      <button type="button">inside</button>
    </Trapped>,
  )

  expect(document.activeElement).toBe(opener)
  opener.remove()
})

test('Tab from the last focusable wraps round to the first', () => {
  render(
    <Trapped>
      <button type="button">first</button>
      <button type="button">last</button>
    </Trapped>,
  )
  const last = screen.getByRole('button', { name: 'last' })
  last.focus()

  fireEvent.keyDown(document, { key: 'Tab' })

  expect(document.activeElement).toHaveTextContent('first')
})

test('Shift+Tab from the first focusable wraps back to the last', () => {
  render(
    <Trapped>
      <button type="button">first</button>
      <button type="button">last</button>
    </Trapped>,
  )

  fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })

  expect(document.activeElement).toHaveTextContent('last')
})

test('Tab in the middle of the dialog is left to the browser', () => {
  render(
    <Trapped>
      <button type="button">first</button>
      <button type="button">middle</button>
      <button type="button">last</button>
    </Trapped>,
  )

  const event = createEvent.keyDown(document, { key: 'Tab' })
  fireEvent(document, event)

  expect(event.defaultPrevented).toBe(false)
})

// The filter sheet grows and shrinks as groups expand, so the focusable set
// cannot be captured once when the trap opens.
test('sees elements added after it opened', () => {
  function Growing() {
    const [expanded, setExpanded] = React.useState(false)
    const ref = React.useRef(null)
    useFocusTrap(true, ref)
    return (
      <div ref={ref}>
        <button type="button" onClick={() => setExpanded(true)}>
          expand
        </button>
        {expanded && <button type="button">revealed</button>}
      </div>
    )
  }
  render(<Growing />)
  fireEvent.click(screen.getByRole('button', { name: 'expand' }))
  screen.getByRole('button', { name: 'revealed' }).focus()

  fireEvent.keyDown(document, { key: 'Tab' })

  expect(document.activeElement).toHaveTextContent('expand')
})

test('locks page scroll while open and restores it on close', () => {
  document.body.style.overflow = 'auto'

  const { unmount } = render(
    <Trapped>
      <button type="button">inside</button>
    </Trapped>,
  )
  expect(document.body.style.overflow).toBe('hidden')

  unmount()

  expect(document.body.style.overflow).toBe('auto')
})

// A ConfirmModal is raised from inside the recipe detail Modal. Closing the
// confirmation must not hand scrolling back to a page that is still covered.
test('keeps the page locked while an outer trap is still open', () => {
  document.body.style.overflow = ''

  const { unmount: closeOuter } = render(
    <Trapped>
      <button type="button">outer</button>
    </Trapped>,
  )
  const { unmount: closeInner } = render(
    <Trapped>
      <button type="button">inner</button>
    </Trapped>,
  )

  closeInner()
  expect(document.body.style.overflow).toBe('hidden')

  closeOuter()
  expect(document.body.style.overflow).toBe('')
})
