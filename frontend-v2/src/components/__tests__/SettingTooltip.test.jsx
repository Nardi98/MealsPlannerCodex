/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import SettingTooltip, { HOVER_DELAY_MS } from '../SettingTooltip'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  cleanup()
})

// jsdom gives every element a zero rect; the anchor needs a real one for the
// placement assertions below.
const ANCHOR_RECT = { top: 400, left: 300, width: 260, height: 90 }
const TOOLTIP_HEIGHT = 120

function stubRects() {
  Element.prototype.getBoundingClientRect = function () {
    const isTooltip = this.getAttribute('role') === 'tooltip'
    const box = isTooltip
      ? { top: 0, left: 0, width: 300, height: TOOLTIP_HEIGHT }
      : ANCHOR_RECT
    return { ...box, right: box.left + box.width, bottom: box.top + box.height, x: box.left, y: box.top }
  }
}

function renderTooltip(props = {}) {
  stubRects()
  return render(
    <SettingTooltip title="Variety" body="How hard the planner avoids repeats." {...props}>
      <label>
        Variety
        <input type="range" aria-label="variety" />
      </label>
    </SettingTooltip>,
  )
}

function settle(ms) {
  return act(async () => {
    vi.advanceTimersByTime(ms)
  })
}

const anchor = () => screen.getByLabelText('variety').closest('[data-setting-tooltip]')
const tip = () => screen.queryByRole('tooltip')

test('nothing is shown until the pointer has rested on the setting for the full delay', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS - 100)
  expect(tip()).not.toBeInTheDocument()
  await settle(200)
  expect(tip()).toBeInTheDocument()
})

test('the delay is a couple of seconds', () => {
  expect(HOVER_DELAY_MS).toBeGreaterThanOrEqual(1500)
})

test('leaving before the delay elapses never shows the tooltip', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS - 100)
  fireEvent.pointerLeave(anchor())
  await settle(5000)
  expect(tip()).not.toBeInTheDocument()
})

test('the tooltip disappears as soon as the pointer leaves', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  expect(tip()).toBeInTheDocument()
  fireEvent.pointerLeave(anchor())
  expect(tip()).not.toBeInTheDocument()
})

test('the tooltip never covers the control it describes', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  const top = parseFloat(tip().style.top)
  expect(top + TOOLTIP_HEIGHT).toBeLessThanOrEqual(ANCHOR_RECT.top)
})

test('it renders the title and body', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  expect(tip()).toHaveTextContent('Variety')
  expect(tip()).toHaveTextContent('How hard the planner avoids repeats.')
})

test('presets are listed with their labels', async () => {
  renderTooltip({ presets: [{ label: 'Repeat freely', text: 'Half the usual penalty.' }] })
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  expect(tip()).toHaveTextContent('Repeat freely')
  expect(tip()).toHaveTextContent('Half the usual penalty.')
})

test('keyboard focus shows it right away, and blur hides it', async () => {
  renderTooltip()
  fireEvent.focus(screen.getByLabelText('variety'))
  expect(tip()).toBeInTheDocument()
  fireEvent.blur(screen.getByLabelText('variety'))
  expect(tip()).not.toBeInTheDocument()
})

test('a long press on touch shows it, and a short tap does not', async () => {
  renderTooltip()
  fireEvent.touchStart(anchor())
  await settle(300)
  fireEvent.touchEnd(anchor())
  await settle(5000)
  expect(tip()).not.toBeInTheDocument()

  fireEvent.touchStart(anchor())
  await settle(HOVER_DELAY_MS)
  expect(tip()).toBeInTheDocument()
})

test('a mouse press on the control dismisses it so it cannot get in the way of a drag', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  fireEvent.pointerDown(anchor())
  expect(tip()).not.toBeInTheDocument()
})

test('Escape dismisses it', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(tip()).not.toBeInTheDocument()
})

test('scrolling dismisses it rather than leaving it behind', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  fireEvent.scroll(document)
  expect(tip()).not.toBeInTheDocument()
})

test('the tooltip is described-by wired to the control and cannot swallow pointer events', async () => {
  renderTooltip()
  fireEvent.pointerEnter(anchor(), { pointerType: 'mouse' })
  await settle(HOVER_DELAY_MS)
  expect(anchor()).toHaveAttribute('aria-describedby', tip().id)
  expect(tip().style.pointerEvents).toBe('none')
})

test('the wrapper keeps the class names it is given, so grid spans survive', () => {
  renderTooltip({ className: 'col-span-2' })
  expect(anchor()).toHaveClass('col-span-2')
})
