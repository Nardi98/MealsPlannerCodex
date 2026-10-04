import React from 'react'
import { ArrowLeftIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import ToggleChip from '../components/ToggleChip'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import { mutedTextStyle, sectionHeadingStyle } from '../components/catalog/textStyles'
import { useFeedbackBadge } from '../components/feedback/FeedbackBadgeContext'
import { useIsMobile } from '../hooks/useIsMobile'
import { apiErrorText, asSentence } from '../api/catalogApi'
import { userFeedbackAdminApi } from '../api/userFeedbackAdminApi'

// Each enumeration's wire value, its words, and its Badge tone, in the order the
// selects offer them. Tones: a type is a category, so it takes a category hue;
// a status runs from the neutral caramel (nothing decided yet) to the guide's
// positive forest (fixed), with sage -- the quieter green -- for set aside.
const TYPES = [
  ['issue', 'Issue', 'terracotta'],
  ['request', 'Request', 'sky'],
  ['improvement', 'Improvement', 'teal'],
  ['not_working', 'Not working', 'danger'],
]
const STATUSES = [
  ['open', 'Open', 'caramel'],
  ['in_progress', 'In progress', 'plum'],
  ['closed_fixed', 'Closed: fixed', 'forest'],
  ['closed_ignored', 'Closed: ignored', 'sage'],
]
const PRIORITIES = [
  ['low', 'Low'],
  ['normal', 'Normal'],
  ['high', 'High'],
]

const lookup = (table) => Object.fromEntries(table.map(([value, ...rest]) => [value, rest]))
const TYPE = lookup(TYPES)
const STATUS = lookup(STATUSES)
const PRIORITY = lookup(PRIORITIES)

const NO_FILTERS = { status: '', type: '', priority: '', tag: '', unreadOnly: false }

/** "4 Sep 2026" in whoever's locale is reading, or nothing for a missing date. */
const shownDate = (value) => {
  if (!value) return ''
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? String(value)
    : parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/** Who sent it. The item outlives the account, so a missing author is normal. */
const authorName = (author) =>
  author ? author.username || author.display_name || author.email : 'Deleted account'

/**
 * The server's tag normalization, repeated so a name the item already has is
 * recognised before a round-trip. The server stays the authority: whatever it
 * answers is what the row shows.
 */
const normalizeTag = (name) => name.trim().toLowerCase().replace(/\s+/g, ' ')

/**
 * Triage of what testers sent in: a filtered list on the left and the selected
 * item on the right, where it is read, prioritised, tagged and closed.
 *
 * A split pane rather than the list + modal of the other admin screens, because
 * triage is reading many items in a row: the detail stays put while the list is
 * walked. Below the `md` breakpoint there is no room for both, so the list
 * gives way to the detail and a back control returns to it.
 *
 * Opening an unread item marks it read and takes one off the sidebar badge;
 * "Mark unread" puts it back. Read and status are separate axes -- closing an
 * item does not read it.
 */
export default function FeedbackAdminPage() {
  const isMobile = useIsMobile()
  const badge = useFeedbackBadge()
  const headingId = React.useId()

  const [rows, setRows] = React.useState(null)
  const [failed, setFailed] = React.useState(false)
  const [reloadKey, setReloadKey] = React.useState(0)
  const [filters, setFilters] = React.useState(NO_FILTERS)
  // The feedback tag vocabulary, for the tag filter and the tag input.
  const [vocabulary, setVocabulary] = React.useState([])
  // { kind: 'status' | 'alert', text } -- the kind doubles as the ARIA role.
  const [notice, setNotice] = React.useState(null)
  const [busy, setBusy] = React.useState(false)
  const [selectedId, setSelectedId] = React.useState(null)

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    const { unreadOnly, ...rest } = filters
    userFeedbackAdminApi
      .list({ ...rest, seen: unreadOnly ? false : undefined })
      .then((result) => {
        if (stale) return
        setRows(result)
        setFailed(false)
      })
      .catch((err) => {
        console.error('Failed to load the feedback', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [filters, reloadKey])

  // Without the vocabulary the tag filter just offers "All tags", which is no
  // reason to put an error on a screen that otherwise works.
  const loadVocabulary = React.useCallback(() => {
    userFeedbackAdminApi
      .listTags()
      .then((tags) => setVocabulary(tags || []))
      .catch(() => {})
  }, [])
  React.useEffect(loadVocabulary, [loadVocabulary])

  const reload = () => setReloadKey((key) => key + 1)
  const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }))

  const selected = (rows || []).find((row) => row.id === selectedId) || null
  const unread = (rows || []).filter((row) => !row.seen).length

  /**
   * Every mutation has the same shape: busy while it runs, an alert naming
   * what failed otherwise. `body` may return a sentence to report; most edits
   * say nothing, because the control that changed already shows the result.
   * Resolves to whether it worked, so a caller can keep a draft that failed.
   */
  const run = async (what, body) => {
    setBusy(true)
    setNotice(null)
    try {
      const text = await body()
      if (text) setNotice({ kind: 'status', text })
      return true
    } catch (err) {
      console.error(`Failed to ${what}`, err)
      setNotice({ kind: 'alert', text: `Couldn’t ${what}: ${asSentence(apiErrorText(err))}` })
      return false
    } finally {
      setBusy(false)
    }
  }

  /** PATCH one item and put the server's answer in its row. */
  const patch = (row, change, what, report) =>
    run(what, async () => {
      const updated = await userFeedbackAdminApi.update(row.id, change)
      setRows((current) => current.map((r) => (r.id === updated.id ? updated : r)))
      if ('seen' in change && change.seen !== row.seen) badge.adjust(change.seen ? -1 : 1)
      if ('tags' in change) loadVocabulary()
      return report
    })

  const open = (row) => {
    setSelectedId(row.id)
    if (!row.seen) patch(row, { seen: true }, `mark ${row.ref_code} read`)
  }

  const listPane = failed ? (
    <CatalogLoadFailed message="Couldn’t load the feedback." onRetry={reload} />
  ) : (
    <FeedbackList
      rows={rows}
      labelledBy={headingId}
      selectedId={selectedId}
      onOpen={open}
    />
  )

  const detailPane = selected ? (
    <FeedbackDetail
      // Keyed so the drafts and the screenshot belong to one item: moving to
      // another starts them afresh and releases the old blob URL.
      key={selected.id}
      item={selected}
      vocabulary={vocabulary}
      busy={busy}
      onPatch={patch}
    />
  ) : null

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h1 id={headingId} style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Feedback
        </h1>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          {rows === null
            ? 'What testers have sent in from the app.'
            : `${rows.length} shown · ${unread} unread`}
        </p>
      </div>

      {!(isMobile && selected) && (
        <FeedbackFilters filters={filters} vocabulary={vocabulary} onChange={setFilter} />
      )}

      {isMobile ? (
        selected ? (
          <div className="flex flex-col gap-3">
            <div>
              <Button variant="ghost" Icon={ArrowLeftIcon} onClick={() => setSelectedId(null)}>
                Back to the list
              </Button>
            </div>
            {detailPane}
          </div>
        ) : (
          listPane
        )
      ) : (
        <div className="flex items-start gap-4">
          <div className="min-w-0" style={{ flex: '2 1 0' }}>
            {listPane}
          </div>
          <div className="sticky top-5 min-w-0" style={{ flex: '3 1 0' }}>
            {detailPane || (
              <Card>
                <p style={mutedTextStyle}>Select an item to read it here.</p>
              </Card>
            )}
          </div>
        </div>
      )}

      {notice && <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)} />}
    </div>
  )
}

/**
 * The listing's one control bar, built like the catalog admin's: a labelled
 * group of native selects. Every filter runs server-side, so each is a plain
 * value handed back up and nothing here filters rows itself.
 */
function FeedbackFilters({ filters, vocabulary, onChange }) {
  const select = (key, label, allLabel, options) => (
    <Input
      as="select"
      aria-label={label}
      value={filters[key]}
      onChange={(e) => onChange(key, e.target.value)}
    >
      <option value="">{allLabel}</option>
      {options.map(([value, words]) => (
        <option key={value} value={value}>
          {words}
        </option>
      ))}
    </Input>
  )

  return (
    <div
      role="group"
      aria-label="Filter the feedback"
      className="flex flex-wrap items-center gap-2 border-t pt-3"
      style={{ borderColor: 'var(--border-default)' }}
    >
      {select('status', 'Filter by status', 'All statuses', STATUSES)}
      {select('type', 'Filter by type', 'All types', TYPES)}
      {select('priority', 'Filter by priority', 'All priorities', PRIORITIES)}
      {select('tag', 'Filter by tag', 'All tags', vocabulary.map((tag) => [tag.name, tag.name]))}
      <ToggleChip
        size="lg"
        active={filters.unreadOnly}
        onClick={() => onChange('unreadOnly', !filters.unreadOnly)}
      >
        Unread only
      </ToggleChip>
    </div>
  )
}

/**
 * The rows. No table primitive exists, so this is the hand-rolled `ul` inside a
 * flush `Card` that the alpha and catalog admin listings use; each row is one
 * button, because the whole row is what opens the item.
 */
function FeedbackList({ rows, labelledBy, selectedId, onOpen }) {
  if (rows === null) return <p style={mutedTextStyle}>Loading the feedback…</p>

  if (rows.length === 0) {
    return (
      <Card>
        <p style={mutedTextStyle}>No feedback matches these filters.</p>
      </Card>
    )
  }

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <ul aria-labelledby={labelledBy} className="m-0 list-none p-0">
        {rows.map((row, i) => {
          const active = row.id === selectedId
          return (
            <li
              key={row.id}
              style={{ borderTop: i === 0 ? 'none' : '1px solid var(--border-default)' }}
            >
              <button
                type="button"
                aria-current={active ? 'true' : undefined}
                onClick={() => onOpen(row)}
                className="flex w-full flex-col gap-1.5 px-4 py-3 text-left"
                style={{
                  border: 'none',
                  cursor: 'pointer',
                  background: active ? 'var(--surface-sunken)' : 'transparent',
                }}
              >
                <span className="flex min-w-0 items-center gap-2">
                  {!row.seen && <UnreadDot />}
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                    {row.ref_code}
                  </span>
                  <span
                    className="min-w-0"
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontWeight: row.seen ? 'var(--weight-medium)' : 'var(--weight-bold)',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--text-strong)',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {row.title}
                  </span>
                </span>
                <span className="flex flex-wrap items-center gap-1">
                  <TypeBadge type={row.type} />
                  <StatusBadge status={row.status} />
                  {row.tags.map((tag) => (
                    <Badge key={tag} tone="olive">
                      {tag}
                    </Badge>
                  ))}
                </span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                  <PriorityText priority={row.priority} />
                  {` · ${authorName(row.author)} · ${shownDate(row.created_at)}`}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

// Mustard, the guide's accent: the same signal the sidebar's unread pill uses.
function UnreadDot() {
  return (
    <span
      role="img"
      aria-label="Unread"
      className="inline-block shrink-0 rounded-full"
      style={{ width: 8, height: 8, background: 'var(--accent-primary)' }}
    />
  )
}

function TypeBadge({ type }) {
  const [words, tone] = TYPE[type] || [type, 'caramel']
  return <Badge tone={tone}>{words}</Badge>
}

function StatusBadge({ status }) {
  const [words, tone] = STATUS[status] || [status, 'caramel']
  return <Badge tone={tone}>{words}</Badge>
}

// High is the one priority worth catching the eye, so only it takes colour.
function PriorityText({ priority }) {
  const [words] = PRIORITY[priority] || [priority]
  return (
    <span style={priority === 'high' ? { color: 'var(--c-neg)', fontWeight: 'var(--weight-semibold)' } : undefined}>
      {`${words} priority`}
    </span>
  )
}

/**
 * One item, in full, with every triage control. Each control saves on its own
 * through `onPatch` -- except the notes, which are prose and get an explicit
 * Save so a half-written sentence is never sent.
 */
function FeedbackDetail({ item, vocabulary, busy, onPatch }) {
  const titleId = React.useId()
  const [notes, setNotes] = React.useState(item.admin_notes || '')
  const [tagDraft, setTagDraft] = React.useState('')

  const addTag = (event) => {
    event.preventDefault()
    const name = normalizeTag(tagDraft)
    if (!name) return
    if (item.tags.includes(name)) {
      setTagDraft('')
      return
    }
    onPatch(item, { tags: [...item.tags, name] }, 'add the tag').then((ok) => {
      // Cleared only on success, so a refused name need not be retyped.
      if (ok) setTagDraft('')
    })
  }

  const fieldId = (name) => `${titleId}-${name}`
  const author = item.author

  return (
    <Card role="region" aria-labelledby={titleId} className="flex flex-col gap-4">
      <div className="min-w-0">
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>{item.ref_code}</div>
        <h2
          id={titleId}
          style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)', overflowWrap: 'anywhere' }}
        >
          {item.title}
        </h2>
        <p style={{ ...mutedTextStyle, marginTop: 4, fontSize: 'var(--text-xs)' }}>
          {author ? `From ${authorName(author)} (${author.email})` : 'From a deleted account'}
          {` · sent ${shownDate(item.created_at)} · updated ${shownDate(item.updated_at)}`}
        </p>
        <div className="mt-2 flex flex-wrap gap-1">
          <TypeBadge type={item.type} />
          <StatusBadge status={item.status} />
        </div>
      </div>

      <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-strong)', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
        {item.body}
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={fieldId('status')} style={sectionHeadingStyle}>
            Status
          </label>
          <Input
            as="select"
            id={fieldId('status')}
            value={item.status}
            onChange={(e) => onPatch(item, { status: e.target.value }, 'save the status')}
          >
            {STATUSES.map(([value, words]) => (
              <option key={value} value={value}>
                {words}
              </option>
            ))}
          </Input>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={fieldId('priority')} style={sectionHeadingStyle}>
            Priority
          </label>
          <Input
            as="select"
            id={fieldId('priority')}
            value={item.priority}
            onChange={(e) => onPatch(item, { priority: e.target.value }, 'save the priority')}
          >
            {PRIORITIES.map(([value, words]) => (
              <option key={value} value={value}>
                {words}
              </option>
            ))}
          </Input>
        </div>
        <Button
          variant="ghost"
          className="ml-auto"
          onClick={() =>
            onPatch(item, { seen: !item.seen }, item.seen ? 'mark it unread' : 'mark it read')
          }
        >
          {item.seen ? 'Mark unread' : 'Mark read'}
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        <div style={{ ...sectionHeadingStyle, marginBottom: 0 }}>Tags</div>
        {item.tags.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {/* The removable chip of `ActiveFilterChips`: same 44px target. */}
            {item.tags.map((tag) => (
              <button
                key={tag}
                type="button"
                aria-label={`Remove tag ${tag}`}
                onClick={() => onPatch(item, { tags: item.tags.filter((t) => t !== tag) }, 'remove the tag')}
                className="inline-flex min-h-11 items-center gap-1 rounded-full border px-3 text-xs"
                style={{ borderColor: 'var(--border-default)', color: 'var(--text-strong)' }}
              >
                {tag}
                <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
        <form className="flex flex-wrap items-center gap-2" onSubmit={addTag}>
          <Input
            className="min-w-0 flex-1"
            aria-label="Add a tag"
            placeholder="Add a tag — a new name creates it"
            list={fieldId('vocabulary')}
            value={tagDraft}
            onChange={(e) => setTagDraft(e.target.value)}
            autoComplete="off"
          />
          <datalist id={fieldId('vocabulary')}>
            {vocabulary
              .filter((tag) => !item.tags.includes(tag.name))
              .map((tag) => (
                <option key={tag.id} value={tag.name} />
              ))}
          </datalist>
          <Button type="submit" variant="secondary" disabled={busy}>
            Add tag
          </Button>
        </form>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={fieldId('notes')} style={{ ...sectionHeadingStyle, marginBottom: 0 }}>
          Admin notes
        </label>
        <Input
          as="textarea"
          id={fieldId('notes')}
          rows={4}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Private to admins."
        />
        <div className="flex justify-end">
          <Button
            variant="primary"
            disabled={busy}
            onClick={() =>
              onPatch(
                item,
                { admin_notes: notes.trim() || null },
                'save the notes',
                `Saved the notes on ${item.ref_code}.`,
              )
            }
          >
            Save notes
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div style={{ ...sectionHeadingStyle, marginBottom: 0 }}>Captured with it</div>
        <dl className="m-0 grid gap-x-3 gap-y-1" style={{ gridTemplateColumns: 'auto minmax(0, 1fr)', fontSize: 'var(--text-xs)' }}>
          <ContextRow term="Page" value={item.page_path} />
          <ContextRow term="Screen width" value={item.viewport_width == null ? null : `${item.viewport_width} px`} />
          <ContextRow term="Browser" value={item.user_agent} />
        </dl>
        {item.has_screenshot && <Screenshot item={item} />}
      </div>
    </Card>
  )
}

function ContextRow({ term, value }) {
  return (
    <>
      <dt style={{ color: 'var(--text-subtle)' }}>{term}</dt>
      <dd className="m-0" style={{ color: 'var(--text-strong)', overflowWrap: 'anywhere' }}>
        {value ?? 'Not recorded'}
      </dd>
    </>
  )
}

/**
 * The attached screenshot, fetched as bytes with the admin's token -- a plain
 * image URL would go out without the Authorization header and be refused --
 * and shown from a blob URL that is released when the item changes or the page
 * goes away.
 */
function Screenshot({ item }) {
  const [shot, setShot] = React.useState({ src: null, failed: false })

  React.useEffect(() => {
    let stale = false
    let url = null
    userFeedbackAdminApi
      .screenshot(item.id)
      .then((blob) => {
        if (stale) return
        url = URL.createObjectURL(blob)
        setShot({ src: url, failed: false })
      })
      .catch((err) => {
        console.error('Failed to load the screenshot', err)
        if (!stale) setShot({ src: null, failed: true })
      })
    return () => {
      stale = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [item.id])

  if (shot.failed) return <p style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>Couldn’t load the screenshot.</p>
  if (!shot.src) return <p style={mutedTextStyle}>Loading the screenshot…</p>
  return (
    <img
      src={shot.src}
      alt={`Screenshot attached to ${item.ref_code}`}
      style={{
        maxWidth: '100%',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-default)',
      }}
    />
  )
}
