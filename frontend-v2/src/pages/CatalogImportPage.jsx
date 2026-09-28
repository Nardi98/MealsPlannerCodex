import React from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import ConfirmModal from '../components/ConfirmModal'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import { mutedTextStyle } from '../components/catalog/textStyles'
import { apiErrorText, asSentence, catalogApi } from '../api/catalogApi'
import { isImportItemOpen } from '../constants/catalog'

// An item's state → how the overview labels it. `pending` reads as "to review"
// rather than "pending": the label names what the admin has to do about it.
const STATE = {
  pending: { label: 'To review', tone: 'sage' },
  invalid: { label: 'Invalid', tone: 'danger' },
  skipped: { label: 'Skipped', tone: 'caramel' },
  committed: { label: 'Committed', tone: 'forest' },
}

const plural = (count, noun) => `${count} ${noun}${count === 1 ? '' : 's'}`

/**
 * Upload a JSON file of catalog recipes and see what the server made of it.
 *
 * The file is parsed **here**, not posted as multipart: the precedent is
 * `/data/import`, and parsing in the browser means a file that is not JSON at
 * all is named before anything crosses the network.
 *
 * One batch is open at a time, so the page has two faces: the picker when
 * there is nothing staged, and the overview when there is. A batch found on
 * load is shown rather than replaced -- the admin is most likely resuming a
 * review they left half-done, and the only way to throw that away is to say so
 * through the confirmation.
 *
 * Reviewing itself happens on `/discover/import/:batchId`; this page only says
 * what is left to do and links to it.
 */
export default function CatalogImportPage() {
  const [batch, setBatch] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [failed, setFailed] = React.useState(false)
  const [reloadKey, setReloadKey] = React.useState(0)

  // The parsed file waiting to be uploaded: { filename, entries }.
  const [staged, setStaged] = React.useState(null)
  const [busy, setBusy] = React.useState(false)
  // { kind: 'status' | 'alert', text } -- the kind doubles as the ARIA role.
  const [notice, setNotice] = React.useState(null)
  const [confirming, setConfirming] = React.useState(false)

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    setLoading(true)
    catalogApi.imports
      .open()
      .then((open) => {
        if (stale) return
        setBatch(open || null)
        setFailed(false)
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to load the open import batch', err)
        if (stale) return
        setFailed(true)
        setLoading(false)
      })
    return () => {
      stale = true
    }
  }, [reloadKey])

  const chooseFile = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setStaged(null)
    setNotice(null)
    let entries
    try {
      entries = JSON.parse(await file.text())
    } catch {
      setNotice({ kind: 'alert', text: `Couldn't read “${file.name}”: it isn't valid JSON.` })
      return
    }
    if (!Array.isArray(entries)) {
      setNotice({ kind: 'alert', text: `“${file.name}” isn't a list of recipes.` })
      return
    }
    if (entries.length === 0) {
      setNotice({ kind: 'alert', text: `“${file.name}” has no recipes in it.` })
      return
    }
    setStaged({ filename: file.name, entries })
  }

  const upload = async () => {
    if (!staged) return
    setBusy(true)
    setNotice(null)
    try {
      const created = await catalogApi.imports.create(staged.filename, staged.entries)
      setBatch(created)
      setStaged(null)
      setNotice({ kind: 'status', text: `Staged ${plural(created.items.length, 'recipe')} from “${created.filename}”.` })
    } catch (err) {
      console.error("Couldn't upload the import", err)
      const reason = asSentence(apiErrorText(err))
      setNotice({ kind: 'alert', text: `Couldn't upload “${staged.filename}”: ${reason}` })
    } finally {
      setBusy(false)
    }
  }

  const discard = async () => {
    setConfirming(false)
    setBusy(true)
    try {
      await catalogApi.imports.remove(batch.id)
      setBatch(null)
      setNotice({ kind: 'status', text: `Discarded “${batch.filename}”. Nothing was added to the library.` })
    } catch (err) {
      console.error("Couldn't discard the import", err)
      const reason = asSentence(apiErrorText(err))
      setNotice({ kind: 'alert', text: `Couldn't discard “${batch.filename}”: ${reason}` })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Import recipes
        </h1>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          Upload a JSON file in the same shape as the library export. Nothing is added until you have
          reviewed each recipe and committed it; committed recipes land as drafts, invisible in
          Discover until you publish them.
        </p>
      </div>

      {failed ? (
        <CatalogLoadFailed
          message="Couldn't load the import in progress."
          onRetry={() => setReloadKey((key) => key + 1)}
        />
      ) : loading ? (
        <p style={mutedTextStyle}>Loading the import…</p>
      ) : batch ? (
        <BatchOverview batch={batch} busy={busy} onAbandon={() => setConfirming(true)} />
      ) : (
        <UploadCard staged={staged} busy={busy} onChoose={chooseFile} onUpload={upload} />
      )}

      {notice && <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)} />}

      {confirming && batch && (
        <ConfirmModal
          title={`Discard ${batch.filename}?`}
          message={
            `Everything still to review in “${batch.filename}” is thrown away, edits included. ` +
            'Recipes you have already committed stay in the library as drafts.'
          }
          confirmLabel="Discard import"
          onConfirm={discard}
          onCancel={() => setConfirming(false)}
        />
      )}
    </div>
  )
}

/** The picker, and what was found in the chosen file before it is sent. */
function UploadCard({ staged, busy, onChoose, onUpload }) {
  return (
    <Card className="flex flex-col gap-3">
      <h2 style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>
        Choose a file
      </h2>
      <Input type="file" accept="application/json,.json" aria-label="Choose a recipe file" onChange={onChoose} />
      <p style={mutedTextStyle}>
        {staged
          ? `“${staged.filename}” holds ${plural(staged.entries.length, 'recipe')}.`
          : 'A JSON file holding a list of recipes.'}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={!staged || busy} onClick={onUpload}>
          {busy ? 'Uploading…' : 'Upload'}
        </Button>
      </div>
    </Card>
  )
}

/**
 * The staged batch: how far the review has got, and every recipe in the file.
 *
 * There is no table primitive, so this is the hand-rolled `ul` inside a flush
 * `Card` the catalog admin listing already uses.
 */
function BatchOverview({ batch, busy, onAbandon }) {
  const headingId = React.useId()
  const items = batch.items || []
  const left = items.filter(isImportItemOpen).length
  const reviewed = items.length - left

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <h2
            id={headingId}
            style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}
          >
            Recipes in this file
          </h2>
          <p style={{ ...mutedTextStyle, marginTop: 4 }}>
            <span style={{ color: 'var(--text-strong)' }}>{batch.filename}</span>
            {` · ${reviewed} of ${items.length} reviewed · ${left} left`}
          </p>
        </div>
        <Button variant="ghost" disabled={busy} onClick={onAbandon}>
          Abandon import
        </Button>
      </div>

      <Card style={{ padding: 0 }}>
        <ul aria-labelledby={headingId} className="m-0 list-none p-0">
          {items.map((item, i) => {
            const state = STATE[item.state] || STATE.pending
            const detail = item.error || (item.problems || []).join(' · ')
            return (
              <li
                key={item.id}
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
                    }}
                  >
                    {item.title || 'Untitled recipe'}
                  </div>
                  {detail && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>{detail}</div>
                  )}
                </div>
                {item.duplicate_recipe_id != null && <Badge tone="gold">Duplicate</Badge>}
                <Badge tone={state.tone}>{state.label}</Badge>
                {isImportItemOpen(item) && (
                  <Link
                    to={`/discover/import/${batch.id}`}
                    className="inline-flex min-h-11 items-center justify-center border px-3 py-2 text-sm shadow-sm hover:opacity-95 font-[family:var(--font-display)]"
                    style={{
                      color: 'var(--text-strong)',
                      borderColor: 'var(--border)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    Review
                  </Link>
                )}
              </li>
            )
          })}
        </ul>
      </Card>
    </section>
  )
}
