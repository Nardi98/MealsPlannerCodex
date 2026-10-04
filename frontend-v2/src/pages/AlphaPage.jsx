// ALPHA-GATE: the closed-alpha signup allowlist screen. Deleted whole when the
// alpha ends (docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md).
import React from 'react'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import ConfirmModal from '../components/ConfirmModal'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import { mutedTextStyle } from '../components/catalog/textStyles'
import { asSentence } from '../api/catalogApi'
import { alphaApi } from '../api/alphaApi'
import { useAdminAction } from '../hooks/useAdminAction'
import { shownDate } from '../utils/formatDate'

/**
 * What a batch add did, in one sentence: only the parts that happened.
 *
 * The three lists are named in full rather than counted, because an admin who
 * has just pasted twenty lines needs to know *which* line was rejected, and
 * the server is the only thing that knows how it split the text.
 */
function addSummary({ added = [], skipped_duplicates: skipped = [], invalid = [] }) {
  const parts = []
  if (added.length) parts.push(`Invited ${added.join(', ')}`)
  if (skipped.length) parts.push(`already listed: ${skipped.join(', ')}`)
  if (invalid.length) parts.push(`not an email address: ${invalid.join(', ')}`)
  if (!parts.length) return 'Nothing to add.'
  return asSentence(parts.join(' · '))
}

/**
 * The closed alpha's guest list, maintained from a page instead of a database
 * client.
 *
 * Only addresses listed here may create an account -- except that an empty list
 * lets everybody in, which is the gate failing open so a wiped database can
 * never lock out every prospective user. That case is the one thing this screen
 * says loudly, because it is invisible everywhere else.
 *
 * Deleting a row only closes a future signup. Accounts already created keep
 * working, and the confirmation says so.
 */
export default function AlphaPage() {
  const [invites, setInvites] = React.useState(null)
  const [failed, setFailed] = React.useState(false)
  const [reloadKey, setReloadKey] = React.useState(0)

  const [draft, setDraft] = React.useState('')
  // { kind: 'status' | 'alert', text } -- the kind doubles as the ARIA role.
  const [notice, setNotice] = React.useState(null)
  // The row whose note is open for editing, and the text so far.
  const [editing, setEditing] = React.useState(null)
  const [pendingDelete, setPendingDelete] = React.useState(null)

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    alphaApi
      .list()
      .then((rows) => {
        if (stale) return
        setInvites(rows)
        setFailed(false)
      })
      .catch((err) => {
        console.error('Failed to load the alpha invites', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [reloadKey])

  const reload = () => setReloadKey((key) => key + 1)

  const signedUp = (invites || []).filter((row) => row.signed_up).length

  // Every mutation reports what happened and then re-reads the list.
  const { busy, run } = useAdminAction(setNotice, { onSuccess: reload })

  const submitAdd = (event) => {
    event.preventDefault()
    return run('add the invites', async () => {
      const result = await alphaApi.add(draft)
      // Cleared only on success: a failed paste is the one thing nobody wants
      // to retype.
      setDraft('')
      return addSummary(result || {})
    })
  }

  const saveNote = (row, text) =>
    run('save the note', async () => {
      await alphaApi.updateNote(row.id, text.trim() || null)
      setEditing(null)
      return `Saved the note for ${row.email}.`
    })

  const confirmDelete = () => {
    const row = pendingDelete
    setPendingDelete(null)
    return run('remove the invite', async () => {
      await alphaApi.remove(row.id)
      return `Removed the invite for ${row.email}.`
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Alpha invites
        </h1>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          {invites === null
            ? 'The addresses allowed to create an account during the closed alpha.'
            : `${invites.length} invited · ${signedUp} signed up`}
        </p>
      </div>

      <Card>
        <form className="flex flex-col gap-3" onSubmit={submitAdd}>
          <label htmlFor="alpha-emails" style={mutedTextStyle}>
            One address per line, or separated by commas.
          </label>
          <Input
            as="textarea"
            id="alpha-emails"
            aria-label="Email addresses to invite"
            rows={4}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={'friend@example.com\nanother@example.com'}
          />
          <div className="flex justify-end">
            <Button type="submit" variant="primary" disabled={busy}>
              Add invites
            </Button>
          </div>
        </form>
      </Card>

      {failed ? (
        <CatalogLoadFailed message="Couldn’t load the alpha invites." onRetry={reload} />
      ) : (
        <InviteList
          rows={invites}
          editing={editing}
          busy={busy}
          onEdit={setEditing}
          onSaveNote={saveNote}
          onDelete={setPendingDelete}
        />
      )}

      {notice && <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)} />}

      {pendingDelete && (
        <ConfirmModal
          title={`Remove ${pendingDelete.email}?`}
          message={
            'This only closes a future signup: it does not remove an existing account, ' +
            'and an account already created keeps working.'
          }
          confirmLabel="Delete invite"
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  )
}

/**
 * The guest list. No table primitive exists, so this is the hand-rolled `ul`
 * inside a flush `Card` that the catalog admin listings already use.
 *
 * `rows` is null until the first load lands. An empty list is not an empty
 * state but a warning: it is the shape of the database in which the gate lets
 * everyone through.
 */
function InviteList({ rows, editing, busy, onEdit, onSaveNote, onDelete }) {
  const headingId = React.useId()

  if (rows === null) return <p style={mutedTextStyle}>Loading the invites…</p>

  if (rows.length === 0) {
    return (
      <Card>
        <p role="alert" style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-neg)' }}>
          There are no invites, so signup is open to everyone. The gate fails open on an empty
          list — add an address to close it.
        </p>
      </Card>
    )
  }

  return (
    <section className="flex flex-col gap-3">
      <h2
        id={headingId}
        style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}
      >
        Invited addresses
      </h2>

      <Card style={{ padding: 0 }}>
        <ul aria-labelledby={headingId} className="m-0 list-none p-0">
          {rows.map((row, i) => (
            <li
              key={row.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3"
              style={{ borderTop: i === 0 ? 'none' : '1px solid var(--border-default)' }}
            >
              <div className="min-w-0 flex-1">
                <div
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontWeight: 'var(--weight-semibold)',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--text-strong)',
                    overflowWrap: 'anywhere',
                  }}
                >
                  {row.email}
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                  {`Added ${shownDate(row.created_at)}`}
                  {row.signed_up && row.signed_up_at
                    ? ` · signed up ${shownDate(row.signed_up_at)}`
                    : ''}
                </div>
              </div>

              {/* Forest is --c-pos, the design guide's positive; caramel is the
                  neutral --c-a3, so "Invited" states a fact without claiming
                  anything has gone right or wrong yet. */}
              <Badge tone={row.signed_up ? 'forest' : 'caramel'}>
                {row.signed_up ? 'Signed up' : 'Invited'}
              </Badge>

              {/* One wrapper, two contents: the reading and editing rows must
                  keep identical geometry, so the classes live in one place. */}
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                {editing?.id === row.id ? (
                  <>
                    <Input
                      className="min-w-0 flex-1"
                      aria-label={`Note for ${row.email}`}
                      value={editing.note}
                      onChange={(event) => onEdit({ id: row.id, note: event.target.value })}
                      autoComplete="off"
                    />
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() => onSaveNote(row, editing.note)}
                    >
                      Save note
                    </Button>
                    <Button variant="ghost" onClick={() => onEdit(null)}>
                      Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <span className="min-w-0 flex-1" style={{ ...mutedTextStyle, fontSize: 'var(--text-xs)' }}>
                      {row.note || 'No note'}
                    </span>
                    <Button
                      variant="ghost"
                      onClick={() => onEdit({ id: row.id, note: row.note || '' })}
                    >
                      Edit note
                    </Button>
                    <Button variant="ghost" onClick={() => onDelete(row)}>
                      Delete
                    </Button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  )
}
