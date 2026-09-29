import React from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import { IngredientDropdown } from '../components/NewRecipeModal'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import { CatalogNoticeText } from '../components/catalog/CatalogNoticeBar'
import SystemIngredientForm from '../components/catalog/SystemIngredientForm'
import { mutedTextStyle, sectionHeadingStyle } from '../components/catalog/textStyles'
import { apiErrorText, catalogApi } from '../api/catalogApi'
import { recipesApi } from '../api/recipesApi'
import { isImportItemOpen } from '../constants/catalog'
import { COURSES } from '../constants/recipeImport'

// The units a stored quantity may carry -- one per dimension, as the server
// spells them (`catalog_import.UNITS`).
const UNITS = ['g', 'ml', 'piece']

const EMPTY_LINE = { name: '', quantity: null, unit: 'g', ingredient_id: null }

// A quantity field's text -> what the draft stores; a blank is "not given".
const asQuantity = (text) => (String(text).trim() === '' ? null : Number(text))

const openItems = (items) => (items || []).filter(isImportItemOpen)

/** The next open item after `fromId` in the batch's stable order, or null. */
const nextOpen = (rows, fromId) => {
  const remaining = openItems(rows)
  const at = remaining.findIndex((row) => row.id === fromId)
  return remaining[at + 1] || remaining.find((row) => row.id !== fromId) || null
}

/** One ingredient line as a sentence: "4 piece Carrot". */
const lineText = (line) => [line.quantity, line.unit, line.name].filter(Boolean).join(' ')

/**
 * The full-page review of one staged import item.
 *
 * Left, the incoming recipe as an editable form; right, the catalog entry it
 * collides with, read-only, so the two can be compared without leaving.
 */
export default function CatalogImportReviewPage() {
  const { batchId } = useParams()
  const navigate = useNavigate()

  const [batch, setBatch] = React.useState(null)
  const [currentId, setCurrentId] = React.useState(null)
  const [item, setItem] = React.useState(null)
  const [draft, setDraft] = React.useState(null)
  const [failed, setFailed] = React.useState(false)
  const [system, setSystem] = React.useState([])
  const [busy, setBusy] = React.useState(false)
  // { kind: 'status' | 'alert', text } -- the kind doubles as the ARIA role.
  const [notice, setNotice] = React.useState(null)
  // The ingredient line index whose "create new" form is open, or null.
  const [creating, setCreating] = React.useState(null)
  const [createError, setCreateError] = React.useState(null)
  const [uploading, setUploading] = React.useState(false)
  const [tagDraft, setTagDraft] = React.useState('')

  React.useEffect(() => {
    let stale = false
    catalogApi.admin
      .ingredients()
      .then((rows) => !stale && setSystem(rows))
      .catch((err) => console.error('Failed to load the system ingredients', err))
    return () => {
      stale = true
    }
  }, [])

  React.useEffect(() => {
    let stale = false
    catalogApi.imports
      .get(batchId)
      .then((next) => {
        if (stale) return
        setBatch(next)
        const open = openItems(next.items)
        // Nothing left to review: the server prunes a finished batch, so this
        // page must stop pointing at it rather than fetch a 404.
        if (!open.length) navigate('/discover/import', { replace: true })
        else setCurrentId(open[0].id)
      })
      .catch((err) => {
        console.error('Failed to load the import batch', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [batchId, navigate])

  React.useEffect(() => {
    if (currentId == null) return undefined
    let stale = false
    setItem(null)
    setDraft(null)
    setCreating(null)
    catalogApi.imports
      .item(batchId, currentId)
      .then((detail) => {
        if (stale) return
        setItem(detail)
        setDraft(detail.draft || {})
      })
      .catch((err) => {
        console.error('Failed to load the staged item', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [batchId, currentId])

  if (failed) return <CatalogLoadFailed message="Couldn't load this import." onRetry={() => navigate(0)} />
  if (!item || !draft) return <p style={mutedTextStyle}>Loading…</p>

  const set = (key) => (event) => setDraft((current) => ({ ...current, [key]: event.target.value }))

  const lines = Array.isArray(draft.ingredients) ? draft.ingredients : []

  const setLine = (index, changes) =>
    setDraft((current) => ({
      ...current,
      ingredients: (current.ingredients || []).map((line, i) => (i === index ? { ...line, ...changes } : line)),
    }))

  // Naming an ingredient the catalog does not own yet, without leaving the
  // review: the row is created in the system account and the line resolves
  // onto it at once, so the same pass that spots the gap fills it.
  const createIngredient = async (index, ingredient) => {
    setBusy(true)
    setCreateError(null)
    try {
      const created = await catalogApi.admin.createIngredient(ingredient)
      setSystem((current) => [...current, created])
      setLine(index, { name: created.name, ingredient_id: created.id })
      setCreating(null)
    } catch (err) {
      console.error('Failed to create the system ingredient', err)
      setCreateError(`Couldn't create it: ${apiErrorText(err)}`)
    } finally {
      setBusy(false)
    }
  }

  const addTag = () => {
    const name = tagDraft.trim()
    if (!name) return
    setDraft((current) => ({
      ...current,
      tags: (current.tags || []).includes(name) ? current.tags : [...(current.tags || []), name],
    }))
    setTagDraft('')
  }

  // The same upload the recipe form uses: the bytes land in the app's own
  // storage and the draft keeps the URL it answers with. Nothing is fetched
  // server-side, so an `image_url` the file carried stays exactly as it came.
  const pickImage = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setNotice(null)
    try {
      const url = await recipesApi.uploadImage(file)
      setDraft((current) => ({ ...current, image_url: url }))
    } catch (err) {
      console.error('Failed to upload the image', err)
      setNotice({ kind: 'alert', text: `Couldn't upload the image: ${apiErrorText(err)}` })
    } finally {
      setUploading(false)
    }
  }

  const save = async () => {
    setBusy(true)
    setNotice(null)
    try {
      // A draft that still does not resolve comes back 200 with `state:
      // "invalid"` -- work in progress is always saved, never refused.
      const next = await catalogApi.imports.saveItem(batchId, item.id, draft)
      setItem(next)
      setDraft(next.draft || {})
      setNotice({ kind: 'status', text: 'Draft saved.' })
    } catch (err) {
      console.error('Failed to save the draft', err)
      setNotice({ kind: 'alert', text: `Couldn't save the draft: ${apiErrorText(err)}` })
    } finally {
      setBusy(false)
    }
  }

  const items = batch?.items || []
  const open = openItems(items)
  const position = open.findIndex((row) => row.id === currentId)

  const goTo = (row) => {
    if (row) setCurrentId(row.id)
    else navigate('/discover/import', { replace: true })
  }

  // Skip and commit answer the same way: the item's new summary, and whether
  // that was the last open one -- in which case the server has pruned the
  // batch and there is nothing here to come back to.
  const resolveItem = async (call, { done, failure }) => {
    setBusy(true)
    setNotice(null)
    try {
      const outcome = await call()
      if (outcome.batch_deleted) {
        navigate('/discover/import', { replace: true })
        return
      }
      const updated = items.map((row) => (row.id === outcome.item.id ? outcome.item : row))
      setBatch((current) => ({ ...current, items: updated }))
      setNotice({ kind: 'status', text: done })
      goTo(nextOpen(updated, outcome.item.id))
    } catch (err) {
      console.error(failure, err)
      setNotice({ kind: 'alert', text: `${failure}: ${apiErrorText(err)}` })
    } finally {
      setBusy(false)
    }
  }

  const next = nextOpen(items, item.id)
  const problems = item.problems || []
  // The server refuses a commit that still has an unresolved name (400 listing
  // every one at once); saying so here means never sending it.
  const blocked = problems.length ? `Can't commit yet: ${problems.join('; ')}` : null

  return (
    <div className="flex flex-col gap-4">
      <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
        Review import
      </h1>
      <p style={mutedTextStyle}>
        {batch?.filename}
        {open.length > 0 && ` · ${position + 1} of ${open.length} left to review`}
      </p>

      {/* One column on a phone, side by side from `md` -- the app's only breakpoint. */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <section aria-label="Incoming recipe" className="flex flex-col gap-3">
            {item.error && (
              <p role="alert" style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>
                The file left this entry unusable: {item.error}
              </p>
            )}
            <div className="flex flex-col gap-1">
              <label htmlFor="import-title" style={mutedTextStyle}>
                Title
              </label>
              <Input id="import-title" value={draft.title || ''} onChange={set('title')} />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="import-course" style={mutedTextStyle}>
                Course
              </label>
              <Input as="select" id="import-course" value={draft.course || ''} onChange={set('course')}>
                {COURSES.map((course) => (
                  <option key={course} value={course}>
                    {course}
                  </option>
                ))}
              </Input>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-1">
                <label htmlFor="import-servings" style={mutedTextStyle}>
                  Servings
                </label>
                <Input
                  id="import-servings"
                  type="number"
                  min="1"
                  step="1"
                  inputMode="numeric"
                  value={draft.servings ?? ''}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, servings: asQuantity(event.target.value) }))
                  }
                />
              </div>
              <label className="flex items-center gap-2 self-end" style={mutedTextStyle}>
                <input
                  type="checkbox"
                  checked={Boolean(draft.bulk_prep)}
                  onChange={(event) => setDraft((current) => ({ ...current, bulk_prep: event.target.checked }))}
                />
                Bulk prep
              </label>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="import-procedure" style={mutedTextStyle}>
                Procedure
              </label>
              <Input
                as="textarea"
                id="import-procedure"
                rows={5}
                value={draft.procedure || ''}
                onChange={set('procedure')}
              />
            </div>

            <div className="flex flex-col gap-2">
              <div style={sectionHeadingStyle}>Tags</div>
              <div className="flex flex-wrap items-center gap-2">
                {(draft.tags || []).map((tag) => (
                  <Badge key={tag} tone="caramel">
                    {tag}
                    <button
                      type="button"
                      aria-label={`Remove tag ${tag}`}
                      style={{ marginLeft: 4, cursor: 'pointer' }}
                      onClick={() =>
                        setDraft((current) => ({
                          ...current,
                          tags: (current.tags || []).filter((name) => name !== tag),
                        }))
                      }
                    >
                      ×
                    </button>
                  </Badge>
                ))}
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <label htmlFor="import-tag" style={mutedTextStyle}>
                    Add a tag
                  </label>
                  <Input id="import-tag" value={tagDraft} onChange={(event) => setTagDraft(event.target.value)} />
                </div>
                <Button variant="ghost" onClick={addTag}>
                  Add tag
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="import-image" style={mutedTextStyle}>
                  Recipe image
                </label>
                <input id="import-image" type="file" accept="image/*" onChange={pickImage} />
              </div>
              {uploading && <span style={mutedTextStyle}>Uploading…</span>}
              {!uploading && draft.image_url && (
                <>
                  <img
                    src={draft.image_url}
                    alt={`${draft.title || 'Recipe'} photo`}
                    style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 'var(--radius-md)' }}
                  />
                  <Button variant="ghost" onClick={() => setDraft((current) => ({ ...current, image_url: null }))}>
                    Remove
                  </Button>
                </>
              )}
            </div>

            {(item.problems || []).length > 0 && (
              <div
                className="flex flex-col gap-1 p-3"
                style={{
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--c-neg)',
                  color: 'var(--c-neg)',
                }}
              >
                <div style={{ ...sectionHeadingStyle, color: 'var(--c-neg)', marginBottom: 0 }}>
                  Still to resolve
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--text-sm)' }}>
                  {item.problems.map((problem) => (
                    <li key={problem}>{problem}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex flex-col gap-2">
              <div style={sectionHeadingStyle}>Ingredients</div>
              {lines.map((line, index) => (
                <div key={index} className="flex flex-wrap items-center gap-2">
                  <IngredientDropdown
                    value={line.name || ''}
                    options={system}
                    // A typed name is a different ingredient: the pick it had
                    // stops applying, so the line is unresolved again.
                    onChange={(name) => setLine(index, { name, ingredient_id: null })}
                    onSelect={(option) => setLine(index, { name: option.name, ingredient_id: option.id })}
                    onAddNew={() => setCreating(index)}
                  />
                  <Input
                    className="w-20"
                    aria-label={`Amount for ${line.name || 'the new line'}`}
                    placeholder="amt"
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    value={line.quantity ?? ''}
                    onChange={(event) => setLine(index, { quantity: asQuantity(event.target.value) })}
                  />
                  <Input
                    as="select"
                    className="w-24"
                    aria-label={`Unit for ${line.name || 'the new line'}`}
                    value={line.unit || ''}
                    onChange={(event) => setLine(index, { unit: event.target.value })}
                  >
                    {UNITS.map((unit) => (
                      <option key={unit} value={unit}>
                        {unit}
                      </option>
                    ))}
                  </Input>
                  {line.ingredient_id == null && <Badge tone="danger">not in the catalog</Badge>}
                  {creating === index && (
                    <Card className="w-full" style={{ marginTop: 8 }}>
                      <SystemIngredientForm
                        key={`new-${index}`}
                        heading="New system ingredient"
                        submitLabel="Create and use"
                        busy={busy}
                        error={createError}
                        onCancel={() => setCreating(null)}
                        onSubmit={(ingredient) => createIngredient(index, ingredient)}
                      />
                    </Card>
                  )}
                </div>
              ))}
              <div>
                <Button
                  variant="ghost"
                  onClick={() => setDraft((current) => ({
                    ...current,
                    ingredients: [...(current.ingredients || []), EMPTY_LINE],
                  }))}
                >
                  + Add ingredient
                </Button>
              </div>
            </div>
          </section>
        </Card>

        {item.duplicate && (
          <Card>
            <section aria-label="Already in the catalog" className="flex flex-col gap-3">
              <h2 style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>
                {item.duplicate.title}
              </h2>
              <p style={mutedTextStyle}>
                {item.duplicate.course} · {item.duplicate.servings} servings
              </p>
              {(item.duplicate.bulk_prep || (item.duplicate.tags || []).length > 0) && (
                <div className="flex flex-wrap gap-1.5">
                  {item.duplicate.bulk_prep && <Badge tone="gold">bulk</Badge>}
                  {(item.duplicate.tags || []).map((tag) => (
                    <Badge key={tag} tone="caramel">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
              <div>
                <div style={sectionHeadingStyle}>Ingredients</div>
                <ul style={{ margin: 0, paddingLeft: 18, ...mutedTextStyle }}>
                  {(item.duplicate.ingredients || []).map((line, i) => (
                    <li key={`${line.name}-${i}`}>{lineText(line)}</li>
                  ))}
                </ul>
              </div>
              {item.duplicate.procedure && (
                <div>
                  <div style={sectionHeadingStyle}>Procedure</div>
                  <p style={{ ...mutedTextStyle, whiteSpace: 'pre-line' }}>{item.duplicate.procedure}</p>
                </div>
              )}
            </section>
          </Card>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <CatalogNoticeText notice={notice} />
        {blocked && (
          <p role="status" className="w-full" style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>
            {blocked}
          </p>
        )}
        <Button variant="ghost" disabled={busy} onClick={save}>
          Save draft
        </Button>
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() =>
            resolveItem(() => catalogApi.imports.skipItem(batchId, item.id), {
              done: 'Skipped.',
              failure: "Couldn't skip it",
            })
          }
        >
          Skip
        </Button>
        <Button
          variant="primary"
          disabled={busy || Boolean(blocked)}
          onClick={() =>
            resolveItem(() => catalogApi.imports.commitItem(batchId, item.id), {
              done: 'Committed as a draft recipe.',
              failure: "Couldn't commit it",
            })
          }
        >
          Commit as draft
        </Button>
        <Button variant="ghost" disabled={busy || !next} onClick={() => goTo(next)}>
          Next
        </Button>
      </div>
    </div>
  )
}
