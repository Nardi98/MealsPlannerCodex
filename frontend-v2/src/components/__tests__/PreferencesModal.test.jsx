/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import PreferencesModal from '../PreferencesModal'

const get = vi.fn()
const update = vi.fn()

vi.mock('../../api/planSettingsApi', () => ({
  planSettingsApi: {
    get: (...a) => get(...a),
    update: (...a) => update(...a),
  },
}))

beforeEach(() => {
  get.mockResolvedValue({ tag_penalty_weight: 0 })
  update.mockResolvedValue({ tag_penalty_weight: 2 })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('loads the stored tag-penalty preset on open', async () => {
  render(<PreferencesModal onClose={() => {}} />)
  await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
  // A weight of 0 corresponds to the "Off" preset being selected.
  await waitFor(() =>
    expect(screen.getByRole('tab', { name: /off/i })).toHaveAttribute('aria-selected', 'true'),
  )
})

test('saves the chosen preset as a weight', async () => {
  render(<PreferencesModal onClose={() => {}} />)
  await waitFor(() => expect(get).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('tab', { name: /strongly reduce/i }))
  fireEvent.click(screen.getByRole('button', { name: /save/i }))
  await waitFor(() =>
    expect(update).toHaveBeenCalledWith({ tag_penalty_weight: 2 }),
  )
})
