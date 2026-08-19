import React from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import { Input } from './Input'
import { sharesApi } from '../api/sharesApi'

/**
 * Share dialog for a single recipe (SH-7 / SH-8 / SH-9 / SH-12 / SH-20).
 *
 * Two rules shape this component:
 *  - SH-7: a link *is* a credential. Naming a recipient alongside a link-mode
 *    share changes nothing about who may open it, and the copy says so.
 *  - The raw token is stored hashed (SH-3), so the URL exists exactly once, in
 *    the creation response. It lives in component state for the lifetime of the
 *    dialog and nowhere else — never logged, stored, or put in a URL.
 */

const MODES = [
  {
    value: 'link',
    label: 'Anyone with the link can open this recipe',
    hint: 'No sign-in needed. Whoever the link reaches — including anyone it is forwarded to — can read it.',
  },
  {
    value: 'person',
    label: 'Only the person I name can open it',
    hint: 'They must be signed in with that email address, so a forwarded link will not work.',
  },
]

const labelStyle = {
  display: 'block',
  fontSize: 'var(--text-sm)',
  fontWeight: 'var(--weight-semibold)',
  color: 'var(--text-strong)',
  marginBottom: 4,
}

const helpStyle = {
  margin: '4px 0 0',
  fontSize: 'var(--text-xs)',
  color: 'var(--text-muted)',
  lineHeight: 1.4,
}

const sectionTitleStyle = {
  fontSize: 'var(--text-sm)',
  fontWeight: 'var(--weight-semibold)',
  color: 'var(--text-strong)',
  marginBottom: 6,
}

function formatDate(value) {
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString()
}

function modeSummary(mode) {
  return mode === 'person'
    ? 'Only the person named can open it'
    : 'Anyone with the link can open it'
}

function ShareRow({ share, onRevoke, busy }) {
  const created = formatDate(share.created_at)
  const lastViewed = formatDate(share.last_viewed_at)
  const expires = formatDate(share.expires_at)
  const revoked = formatDate(share.revoked_at)

  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 12,
        padding: '8px 10px',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--surface-sunken)',
        opacity: share.active ? 1 : 0.65,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }}>
          {modeSummary(share.mode)}
        </div>
        {share.recipient_email && (
          <div
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--text-muted)',
              overflowWrap: 'anywhere',
            }}
          >
            {share.recipient_email}
          </div>
        )}
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
          {created && <span>Created {created}</span>}
          {created && (lastViewed || expires) && ' · '}
          <span>{lastViewed ? `Last viewed ${lastViewed}` : 'Last viewed never'}</span>
          {expires && ` · Expires ${expires}`}
          {!share.active && (revoked ? ` · Revoked ${revoked}` : ' · Revoked or expired')}
        </div>
      </div>
      {share.active && (
        <Button size="sm" variant="danger" disabled={busy} onClick={() => onRevoke(share.id)}>
          Revoke
        </Button>
      )}
    </li>
  )
}

export function ShareRecipeModal({ recipe, open, onClose }) {
  const [mode, setMode] = React.useState('link')
  const [recipient, setRecipient] = React.useState('')
  const [expiresAt, setExpiresAt] = React.useState('')
  // The one and only copy of the raw share URL. Dropped when the dialog closes.
  const [createdUrl, setCreatedUrl] = React.useState('')
  const [copied, setCopied] = React.useState(false)
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [shares, setShares] = React.useState([])

  const recipeId = recipe ? recipe.id : null

  const loadShares = React.useCallback(async () => {
    if (recipeId == null) return
    try {
      const rows = await sharesApi.list(recipeId)
      setShares(Array.isArray(rows) ? rows : [])
    } catch {
      // A failed listing must not block creating a share; the panel just stays
      // empty rather than turning the whole dialog into an error page.
      setShares([])
    }
  }, [recipeId])

  React.useEffect(() => {
    if (!open) {
      // Forget the bearer URL and the form as soon as the dialog goes away.
      setCreatedUrl('')
      setCopied(false)
      setError('')
      setMode('link')
      setRecipient('')
      setExpiresAt('')
      return
    }
    loadShares()
  }, [open, loadShares])

  if (!open) return null

  const handleCreate = async () => {
    setError('')
    if (mode === 'person' && !recipient.trim()) {
      setError('Enter the email address of the person you want to share with.')
      return
    }
    setBusy(true)
    try {
      const share = await sharesApi.create(recipeId, {
        mode,
        recipient_email: recipient,
        expires_at: expiresAt,
      })
      setCreatedUrl((share && share.url) || '')
      setCopied(false)
      await loadShares()
    } catch (err) {
      setError(
        err && err.status === 429
          ? "You've created a lot of shares recently. Give it a few minutes and try again."
          : (err && err.message) || 'Could not create the share.'
      )
    } finally {
      setBusy(false)
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(createdUrl)
      setCopied(true)
    } catch {
      setCopied(false)
      setError('Could not copy automatically — select the link above and copy it.')
    }
  }

  const handleRevoke = async (shareId) => {
    setBusy(true)
    setError('')
    try {
      await sharesApi.revoke(shareId)
      await loadShares()
    } catch (err) {
      setError((err && err.message) || 'Could not revoke the share.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={`Share ${recipe ? recipe.title : 'recipe'}`} onClose={onClose} maxWidth={560}>
      <div className="flex flex-col gap-4">
        {/* SH-8: the two modes are described by what they actually do. */}
        <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
          <legend style={sectionTitleStyle}>Who can open it</legend>
          <div className="flex flex-col gap-2">
            {MODES.map((option) => (
              <label
                key={option.value}
                htmlFor={`share-mode-${option.value}`}
                style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'flex-start',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid',
                  borderColor: mode === option.value ? 'var(--c-a2)' : 'var(--border-default)',
                  cursor: 'pointer',
                }}
              >
                <input
                  id={`share-mode-${option.value}`}
                  type="radio"
                  name="share-mode"
                  value={option.value}
                  checked={mode === option.value}
                  onChange={() => setMode(option.value)}
                  style={{ marginTop: 3 }}
                />
                <span>
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }}>
                    {option.label}
                  </span>
                  <span style={{ ...helpStyle, display: 'block' }}>{option.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label htmlFor="share-recipient" style={labelStyle}>
            {mode === 'person' ? 'Recipient email' : 'Recipient email (optional)'}
          </label>
          <Input
            id="share-recipient"
            type="email"
            className="w-full"
            value={recipient}
            placeholder="name@example.com"
            onChange={(e) => setRecipient(e.target.value)}
          />
          {/* SH-7: the disclosure that naming someone is not an access control. */}
          <p style={helpStyle}>
            {mode === 'person'
              ? 'They will need to be signed in with this address to open the recipe.'
              : 'Naming someone here only adds the recipe to their account, so it appears in their Shared-with-me — it does not restrict who can open the link.'}
          </p>
        </div>

        <div>
          <label htmlFor="share-expires" style={labelStyle}>
            Expires on (optional)
          </label>
          <Input
            id="share-expires"
            type="date"
            value={expiresAt}
            onChange={(e) => setExpiresAt(e.target.value)}
          />
          {/* SH-9: expiry is opt-in; there is deliberately no default. */}
          <p style={helpStyle}>A share never expires unless you set a date here.</p>
        </div>

        {/* Q-4: no photo means a bare unfurl wherever the link is pasted. */}
        {recipe && !recipe.image_url && (
          <p
            style={{
              margin: 0,
              padding: '8px 10px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'color-mix(in srgb, var(--c-a2) 18%, #fff)',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-strong)',
            }}
          >
            This recipe has no photo, so the link will unfurl as a bare text card in chat apps. Add
            one first if you want it to look inviting.
          </p>
        )}

        {error && (
          <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-neg)' }}>{error}</p>
        )}

        <div className="flex justify-end">
          <Button size="sm" variant="primary" disabled={busy} onClick={handleCreate}>
            Create share link
          </Button>
        </div>

        {createdUrl && (
          <div
            style={{
              padding: 12,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--surface-sunken)',
            }}
          >
            <label htmlFor="share-url" style={labelStyle}>
              Your share link
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="share-url"
                className="w-full"
                readOnly
                value={createdUrl}
                onFocus={(e) => e.target.select()}
              />
              <Button size="sm" variant="accent" onClick={handleCopy}>
                Copy link
              </Button>
            </div>
            <p style={helpStyle}>
              This link is shown once and cannot be shown again — copy it now, then send it however
              you like. {copied ? 'Copied.' : ''}
            </p>
          </div>
        )}

        {/* SH-20: every share on this recipe, each individually revocable. */}
        <div>
          <div style={sectionTitleStyle}>Existing shares</div>
          {shares.length === 0 ? (
            <p style={{ ...helpStyle, marginTop: 0 }}>This recipe has not been shared yet.</p>
          ) : (
            <ul className="flex flex-col gap-2" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {shares.map((share) => (
                <ShareRow key={share.id} share={share} onRevoke={handleRevoke} busy={busy} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  )
}

export default ShareRecipeModal
