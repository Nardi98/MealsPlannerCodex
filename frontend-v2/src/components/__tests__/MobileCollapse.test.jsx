/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { stubViewport } from '../../test/stubViewport'
import MobileCollapse from '../MobileCollapse'

afterEach(cleanup)

function setup() {
  render(
    <MobileCollapse title="Plan settings">
      <p>the settings</p>
    </MobileCollapse>,
  )
}

test('renders its children plainly on desktop, with no toggle', () => {
  stubViewport(false)
  setup()

  expect(screen.getByText('the settings')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /plan settings/i })).not.toBeInTheDocument()
})

test('hides its children behind a toggle on mobile', () => {
  stubViewport(true)
  setup()

  expect(screen.queryByText('the settings')).not.toBeInTheDocument()
  const toggle = screen.getByRole('button', { name: /plan settings/i })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
})

test('the toggle opens and closes the section', async () => {
  stubViewport(true)
  setup()

  const toggle = screen.getByRole('button', { name: /plan settings/i })
  await userEvent.click(toggle)
  expect(screen.getByText('the settings')).toBeInTheDocument()
  expect(toggle).toHaveAttribute('aria-expanded', 'true')

  await userEvent.click(toggle)
  expect(screen.queryByText('the settings')).not.toBeInTheDocument()
})

test('starts expanded on mobile when the caller asks for it', () => {
  stubViewport(true)
  render(
    <MobileCollapse title="Plan settings" defaultOpen>
      <p>the settings</p>
    </MobileCollapse>,
  )

  expect(screen.getByText('the settings')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /plan settings/i })).toHaveAttribute('aria-expanded', 'true')
})

test('puts a caller-supplied tour anchor on the toggle, so a collapsed section is still reachable', () => {
  stubViewport(true)
  const { container } = render(
    <MobileCollapse title="Plan settings" tourId="mealplan-settings-toggle">
      <p>the settings</p>
    </MobileCollapse>,
  )
  expect(container.querySelector('[data-tour="mealplan-settings-toggle"]')).not.toBeNull()
})
