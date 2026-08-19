import React from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card } from '../components'
import { sharedWithMeApi } from '../api/sharedWithMeApi'

// In-app landing for a share link (SP-3).
//
// This route is only reached by an already-authenticated user; the signed-out
// experience is the server-rendered share page, which needs no JavaScript. All
// this page does is turn a token in the URL into a copy in the caller's book.
//
// The token is read from the route and passed straight to the request. It is
// never written to localStorage/sessionStorage, never logged, and never
// rendered — a share token is a credential (SH-2/SH-3), and echoing it into the
// DOM would put it in screenshots, in the accessibility tree, and in any
// bug-report tooling that captures page text.
//
// The copy is not fired on mount. It is a deliberate, rate-limited (CP-9) write
// to the user's own book, so it waits for an explicit click; an automatic copy
// would also mean a stray refresh silently duplicates the recipe.

const NEUTRAL_GONE =
  'This recipe is no longer available. The link may have been revoked by the ' +
  'person who shared it, or it may have expired.'

const RATE_LIMITED =
  'Too many copies in a short time. Please wait a moment and try again.'

// Dispatch on `error.status`, never on the message. `client.js`'s request()
// attaches the HTTP status to everything it throws, and the status is the
// contract: 404 means gone, 429 means slow down, in every locale and after any
// rewording. Matching the backend's English prose instead meant this page had
// an undeclared dependency on strings nobody had promised to keep — it would
// have degraded silently the day a message was translated or a proxy replaced
// it, and it misfired the other way too, presenting a 500 that happened to say
// "not found" as a calm "this recipe is gone".
function messageFor(error) {
  if (error.status === 404) {
    // SH-22: revoked, expired, and never-existed are one indistinguishable
    // answer, phrased so it neither confirms nor denies that a recipe exists.
    return { text: NEUTRAL_GONE, tone: 'calm' }
  }
  if (error.status === 429) {
    return { text: RATE_LIMITED, tone: 'alert' }
  }
  // 403 (SH-24, wrong account) and anything else: the backend's own wording is
  // the only thing that tells the user how to fix it.
  return { text: error.message, tone: 'alert' }
}

export function SharedRecipePage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [copying, setCopying] = React.useState(false)
  const [result, setResult] = React.useState(null)
  const [error, setError] = React.useState(null)

  const handleCopy = async () => {
    setCopying(true)
    setError(null)
    setResult(null)
    try {
      setResult(await sharedWithMeApi.copyByToken(token))
    } catch (err) {
      setError(err)
    } finally {
      setCopying(false)
    }
  }

  const notice = error ? messageFor(error) : null

  return (
    <section style={{ maxWidth: 560 }}>
      <h1
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-2xl)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-strong)',
          margin: 0,
        }}
      >
        Shared recipe
      </h1>

      <Card style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {!token && (
          <p role="alert" style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-neg)' }}>
            This share link is missing its token. Ask for the link again.
          </p>
        )}

        {token && (
          <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
            Someone shared a recipe with you. Copying it puts an independent copy
            in your own recipes — you can edit it freely, and later changes to the
            original will not reach it.
          </p>
        )}

        {result && (
          <p
            role="status"
            style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-pos)' }}
          >
            {result.already_copied
              ? `You already had a copy of ${result.title}; a second one has been added to your recipes.`
              : `${result.title} has been added to your recipes.`}
          </p>
        )}

        {notice && (
          <p
            role={notice.tone === 'calm' ? 'status' : 'alert'}
            style={{
              margin: 0,
              fontSize: 'var(--text-sm)',
              color: notice.tone === 'calm' ? 'var(--text-muted)' : 'var(--c-neg)',
            }}
          >
            {notice.text}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          {token && !result && (
            <Button variant="accent" disabled={copying} onClick={handleCopy}>
              {copying ? 'Copying…' : 'Copy to my book'}
            </Button>
          )}
          <Button variant="ghost" onClick={() => navigate('/recipes')}>
            {result ? 'Go to my recipes' : 'Back to my recipes'}
          </Button>
        </div>
      </Card>
    </section>
  )
}

export default SharedRecipePage
