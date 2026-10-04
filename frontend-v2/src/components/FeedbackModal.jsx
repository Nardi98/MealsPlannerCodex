import React from 'react'
import { useLocation } from 'react-router-dom'
import { Modal } from './Modal'
import { Button } from './Button'
import { Input } from './Input'
import SegmentedControl from './SegmentedControl'
import { userFeedbackApi } from '../api/userFeedbackApi'
import { apiErrorText, asSentence } from '../api/catalogApi'
import { fieldHelpStyle, fieldLabelStyle } from './catalog/textStyles'

/**
 * "Send feedback" dialog, opened from the profile menu.
 *
 * It captures its own context (page, viewport, browser) at submit time rather
 * than taking it as props, so the menu that opens it stays ignorant of it. It
 * never fetches on mount: nothing is sent until the user presses Send.
 */

const TYPES = [
  { value: 'issue', label: 'Issue' },
  { value: 'request', label: 'Request' },
  { value: 'improvement', label: 'Improvement' },
  { value: 'not_working', label: 'Not working' },
]

// The rate limit is the one error a well-meaning user hits by being helpful,
// so it gets its own calm copy instead of the server's "Too Many Requests".
function errorText(err) {
  if (err?.status === 429) {
    return "You've sent a lot of feedback recently. Please try again in a little while."
  }
  return `Couldn't send your feedback: ${asSentence(apiErrorText(err))}`
}

export default function FeedbackModal({ onClose }) {
  const { pathname } = useLocation()
  const [title, setTitle] = React.useState('')
  const [body, setBody] = React.useState('')
  const [type, setType] = React.useState('issue')
  const [file, setFile] = React.useState(undefined)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [refCode, setRefCode] = React.useState('')

  const ready = title.trim() !== '' && body.trim() !== ''

  const submit = async (e) => {
    e.preventDefault()
    if (!ready || busy) return
    setError('')
    setBusy(true)
    try {
      const res = await userFeedbackApi.submit(
        {
          title: title.trim(),
          body: body.trim(),
          type,
          page_path: pathname,
          user_agent: navigator.userAgent,
          viewport_width: window.innerWidth,
        },
        file
      )
      setRefCode(res.ref_code)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (refCode) {
    return (
      <Modal title="Feedback sent" onClose={onClose}>
        <p style={{ margin: '0 0 16px', fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }}>
          Thanks — {`your reference is ${refCode}.`}
        </p>
        <div className="flex justify-end">
          <Button onClick={onClose}>Done</Button>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="Send feedback" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <SegmentedControl label="Kind" options={TYPES} value={type} onChange={setType} />
        <div>
          <label htmlFor="feedback-title" style={fieldLabelStyle}>Title</label>
          <Input
            id="feedback-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full"
          />
        </div>
        <div>
          <label htmlFor="feedback-body" style={fieldLabelStyle}>Details</label>
          <Input
            as="textarea"
            id="feedback-body"
            rows={5}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="w-full"
          />
        </div>
        <div>
          <label htmlFor="feedback-screenshot" style={fieldLabelStyle}>Screenshot (optional)</label>
          <input
            id="feedback-screenshot"
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] || undefined)}
            className="block w-full text-sm file:mr-3 file:rounded-xl file:border-0 file:px-3 file:py-2 file:text-sm file:text-white file:bg-[color:var(--c-a1)]"
          />
        </div>
        <p style={{ ...fieldHelpStyle, margin: 0 }}>We'll include the page you're on ({pathname}).</p>
        {error && (
          <p role="alert" className="text-sm" style={{ margin: 0, color: 'var(--c-neg)' }}>
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!ready || busy}>
            {busy ? 'Sending…' : 'Send feedback'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
