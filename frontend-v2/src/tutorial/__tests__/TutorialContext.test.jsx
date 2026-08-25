/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, expect, test } from 'vitest'
import { TutorialProvider, ReplayTutorialButton } from '../TutorialProvider'
import { PageTour } from '../PageTour'
import { markAllToursDone } from '../tourStorage'

const STEPS = [{ target: '[data-tour="x"]', title: 'Only step', body: 'hello' }]

beforeEach(() => localStorage.clear())
afterEach(() => {
  cleanup()
  document.body.innerHTML = ''
})

test('the replay button is hidden on a page with no tour', () => {
  render(
    <TutorialProvider>
      <ReplayTutorialButton />
    </TutorialProvider>,
  )
  expect(screen.queryByRole('button', { name: 'Replay tutorial' })).not.toBeInTheDocument()
})

test('the replay button restarts a tour the user has already finished', () => {
  markAllToursDone()
  render(
    <TutorialProvider>
      <ReplayTutorialButton />
      <PageTour id="recipes" steps={STEPS} />
    </TutorialProvider>,
  )
  expect(screen.queryByText('Only step')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Replay tutorial' }))
  expect(screen.getByText('Only step')).toBeInTheDocument()
})

test('the button disappears again when the page with the tour unmounts', () => {
  markAllToursDone()
  const { rerender } = render(
    <TutorialProvider>
      <ReplayTutorialButton />
      <PageTour id="recipes" steps={STEPS} />
    </TutorialProvider>,
  )
  expect(screen.getByRole('button', { name: 'Replay tutorial' })).toBeInTheDocument()
  rerender(
    <TutorialProvider>
      <ReplayTutorialButton />
    </TutorialProvider>,
  )
  expect(screen.queryByRole('button', { name: 'Replay tutorial' })).not.toBeInTheDocument()
})
