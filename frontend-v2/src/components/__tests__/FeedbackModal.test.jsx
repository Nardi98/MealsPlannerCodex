/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import FeedbackModal from '../FeedbackModal'
import { userFeedbackApi } from '../../api/userFeedbackApi'

vi.mock('../../api/userFeedbackApi', () => ({
  userFeedbackApi: { submit: vi.fn() },
}))

beforeEach(() => {
  userFeedbackApi.submit.mockReset()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function open(props = {}) {
  return render(
    <MemoryRouter initialEntries={['/plan']}>
      <FeedbackModal onClose={() => {}} {...props} />
    </MemoryRouter>
  )
}

const fill = ({ title = 'Plan is empty', body = 'Generated nothing for Monday' } = {}) => {
  fireEvent.change(screen.getByLabelText(/^title$/i), { target: { value: title } })
  fireEvent.change(screen.getByLabelText(/details/i), { target: { value: body } })
}

const send = () => fireEvent.click(screen.getByRole('button', { name: /send feedback/i }))

test('does not call the API on mount', () => {
  open()
  expect(userFeedbackApi.submit).not.toHaveBeenCalled()
})

test('says the current page is included', () => {
  open()
  expect(screen.getByText(/include the page you're on \(\/plan\)/i)).toBeInTheDocument()
})

test('a blank title blocks submit', () => {
  open()
  fill({ title: '   ' })
  send()
  expect(userFeedbackApi.submit).not.toHaveBeenCalled()
})

test('a blank body blocks submit', () => {
  open()
  fill({ body: '  ' })
  send()
  expect(userFeedbackApi.submit).not.toHaveBeenCalled()
})

test('sends the text, the default type and the captured page context', async () => {
  userFeedbackApi.submit.mockResolvedValue({ ref_code: 'FB-104' })
  open()
  fill()
  send()

  await waitFor(() => expect(userFeedbackApi.submit).toHaveBeenCalled())
  const [fields, file] = userFeedbackApi.submit.mock.calls[0]
  expect(fields).toEqual({
    title: 'Plan is empty',
    body: 'Generated nothing for Monday',
    type: 'issue',
    page_path: '/plan',
    user_agent: navigator.userAgent,
    viewport_width: window.innerWidth,
  })
  expect(file).toBeUndefined()
})

test('sends the chosen type', async () => {
  userFeedbackApi.submit.mockResolvedValue({ ref_code: 'FB-1' })
  open()
  fill()
  fireEvent.click(screen.getByRole('tab', { name: /not working/i }))
  send()

  await waitFor(() => expect(userFeedbackApi.submit).toHaveBeenCalled())
  expect(userFeedbackApi.submit.mock.calls[0][0].type).toBe('not_working')
})

test('passes a chosen screenshot through', async () => {
  userFeedbackApi.submit.mockResolvedValue({ ref_code: 'FB-1' })
  const shot = new File(['bytes'], 'shot.png', { type: 'image/png' })
  open()
  fill()
  fireEvent.change(screen.getByLabelText(/screenshot/i), { target: { files: [shot] } })
  send()

  await waitFor(() => expect(userFeedbackApi.submit).toHaveBeenCalled())
  expect(userFeedbackApi.submit.mock.calls[0][1]).toBe(shot)
})

test('disables the submit button while sending', async () => {
  let resolve
  userFeedbackApi.submit.mockReturnValue(new Promise((r) => (resolve = r)))
  open()
  fill()
  send()

  expect(await screen.findByRole('button', { name: /sending/i })).toBeDisabled()
  resolve({ ref_code: 'FB-1' })
  expect(await screen.findByText(/FB-1/)).toBeInTheDocument()
})

test('shows the returned reference and closes on Done', async () => {
  userFeedbackApi.submit.mockResolvedValue({ ref_code: 'FB-104' })
  const onClose = vi.fn()
  open({ onClose })
  fill()
  send()

  expect(await screen.findByText(/your reference is FB-104/i)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /done/i }))
  expect(onClose).toHaveBeenCalled()
})

test('shows an API error and keeps the form open', async () => {
  userFeedbackApi.submit.mockRejectedValue(
    Object.assign(new Error('Screenshot must be an image'), { status: 400 })
  )
  const onClose = vi.fn()
  open({ onClose })
  fill()
  send()

  expect(await screen.findByText(/screenshot must be an image\./i)).toBeInTheDocument()
  expect(screen.getByLabelText(/^title$/i)).toHaveValue('Plan is empty')
  expect(onClose).not.toHaveBeenCalled()
})

test('a rate limit reads calmly', async () => {
  userFeedbackApi.submit.mockRejectedValue(
    Object.assign(new Error('Too Many Requests'), { status: 429 })
  )
  open()
  fill()
  send()

  expect(await screen.findByText(/try again in a little while/i)).toBeInTheDocument()
  expect(screen.queryByText(/too many requests/i)).not.toBeInTheDocument()
})
