import React from 'react'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import ConfirmModal from '../components/ConfirmModal'
import SegmentedControl from '../components/SegmentedControl'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import SystemIngredientForm from '../components/catalog/SystemIngredientForm'
import { mutedTextStyle } from '../components/catalog/textStyles'
import { apiErrorText, catalogApi } from '../api/catalogApi'

const TABS = [
  { value: 'ingredients', label: 'Ingredients' },
  { value: 'tags', label: 'Tags' },
]

const DIMENSION_LABEL = { mass: 'by mass', volume: 'by volume', piece: 'by piece' }

// Ends a reason with exactly one full stop, whether or not it came with one.
const asSentence = (text) => `${String(text).replace(/\.+$/, '')}.`

const norm = (name) => String(name || '').trim().toLowerCase()

/** "no recipes", "1 recipe", "4 recipes" -- the count, as a phrase. */
const uses = (count) => (count === 0 ? 'no recipes' : `${count} recipe${count === 1 ? '' : 's'}`)

/**
 * How many catalog recipes name each ingredient and each tag.
 *
 * Counted here, from the admin listing, because the vocabulary endpoints
 * answer with names alone: the server only reveals a count when it *refuses* a
 * delete, and a confirmation that cannot say what it is about to break is not
 * a confirmation. Names are matched case-insensitively, as the server resolves
 * them.
 */
function usageOf(recipes) {
  const ingredients = new Map()
  const tags = new Map()
  const bump = (map, name) => map.set(norm(name), (map.get(norm(name)) || 0) + 1)
  for (const recipe of recipes || []) {
    for (const line of recipe.ingredients || []) bump(ingredients, line.name)
    for (const tag of recipe.tags || []) bump(tags, tag)
  }
  return { ingredients, tags }
}

/** The one-line summary under an ingredient's name. */
function ingredientMeta(ingredient) {
  const parts = []
  const months = (ingredient.season_months || []).length
  if (months) parts.push(`${months} month${months === 1 ? '' : 's'} in season`)
  if (ingredient.preferred_dimension) parts.push(DIMENSION_LABEL[ingredient.preferred_dimension])
  if (ingredient.grams_per_piece != null) parts.push(`${ingredient.grams_per_piece} g per piece`)
  if (ingredient.grams_per_ml != null) parts.push(`${ingredient.grams_per_ml} g per ml`)
  return parts.join(' · ') || 'Nothing recorded yet'
}

/**
 * The system vocabulary, maintained from a page instead of a database client.
 *
 * Catalog recipes may only name ingredients and tags the system account owns,
 * so this is where that list grows. Every write is admin-only on the server;
 * the page only decides whether to show the controls.
 *
 * The ingredient form is `SystemIngredientForm` rather than markup of its own:
 * the import review page raises the identical form to name an ingredient a
 * file mentions but the catalog does not have yet, and one form means one set
 * of rules about what an ingredient is.
 */
export default function SystemVocabularyPage() {
  const [tab, setTab] = React.useState('ingredients')
  const [search, setSearch] = React.useState('')

  const [ingredients, setIngredients] = React.useState(null)
  const [tags, setTags] = React.useState(null)
  const [usage, setUsage] = React.useState({ ingredients: new Map(), tags: new Map() })
  const [failed, setFailed] = React.useState(false)
  const [reloadKey, setReloadKey] = React.useState(0)

  // { kind: 'status' | 'alert', text } -- the kind doubles as the ARIA role.
  const [notice, setNotice] = React.useState(null)
  // The open form: { kind: 'ingredient' | 'tag', row: the row being edited or null }.
  const [form, setForm] = React.useState(null)
  const [formError, setFormError] = React.useState(null)
  const [busy, setBusy] = React.useState(false)
  // The row a confirmation is standing in front of: { kind, row, count }.
  const [pendingDelete, setPendingDelete] = React.useState(null)

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    Promise.all([catalogApi.admin.ingredients(), catalogApi.admin.tags(), catalogApi.admin.list({})])
      .then(([nextIngredients, nextTags, recipes]) => {
        if (stale) return
        setIngredients(nextIngredients)
        setTags(nextTags)
        setUsage(usageOf(recipes))
        setFailed(false)
      })
      .catch((err) => {
        console.error('Failed to load the system vocabulary', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [reloadKey])

  const reload = () => setReloadKey((key) => key + 1)

  const closeForm = () => {
    setForm(null)
    setFormError(null)
  }

  // Every write here answers the same way: report it, close the form that
  // raised it and reload, or leave the form open with the reason.
  const write = async (call, { done, failure, keepOpen = false }) => {
    setBusy(true)
    setNotice(null)
    setFormError(null)
    try {
      await call()
      setNotice({ kind: 'status', text: done })
      if (!keepOpen) closeForm()
      reload()
    } catch (err) {
      console.error(failure, err)
      const text = `${failure}: ${asSentence(apiErrorText(err))}`
      if (keepOpen) setNotice({ kind: 'alert', text })
      else setFormError(text)
    } finally {
      setBusy(false)
    }
  }

  const saveIngredient = (changes) => {
    const row = form.row
    if (row) {
      if (Object.keys(changes).length === 0) {
        closeForm()
        return
      }
      return write(() => catalogApi.admin.updateIngredient(row.id, changes), {
        done: `Saved “${row.name}”.`,
        failure: `Couldn't save “${row.name}”`,
      })
    }
    return write(() => catalogApi.admin.createIngredient(changes), {
      done: `Added “${changes.name}” to the vocabulary.`,
      failure: `Couldn't add “${changes.name}”`,
    })
  }

  const saveTag = (changes) => {
    const row = form.row
    if (row) {
      if (Object.keys(changes).length === 0) {
        closeForm()
        return
      }
      return write(() => catalogApi.admin.updateTag(row.id, changes), {
        done: `Saved “${row.name}”.`,
        failure: `Couldn't save “${row.name}”`,
      })
    }
    return write(() => catalogApi.admin.createTag(changes), {
      done: `Added “${changes.name}” to the vocabulary.`,
      failure: `Couldn't add “${changes.name}”`,
    })
  }

  const confirmDelete = () => {
    const { kind, row } = pendingDelete
    setPendingDelete(null)
    const remove = kind === 'ingredient' ? catalogApi.admin.deleteIngredient : catalogApi.admin.deleteTag
    return write(() => remove(row.id), {
      done: `Deleted “${row.name}”.`,
      failure: `Couldn't delete “${row.name}”`,
      keepOpen: true,
    })
  }

  const query = norm(search)
  const match = (rows) => (rows || []).filter((row) => norm(row.name).includes(query))
  const shownIngredients = ingredients === null ? null : match(ingredients)
  const shownTags = tags === null ? null : match(tags)

  const askDelete = (kind, row) =>
    setPendingDelete({ kind, row, count: usage[`${kind}s`].get(norm(row.name)) || 0 })

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Ingredients &amp; tags
        </h1>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          The words the library is allowed to use. A catalog recipe can only name what is on these
          lists, and an ingredient&apos;s seasons and weights are what the planner and the shopping
          list do their arithmetic with.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <SegmentedControl label="Vocabulary" options={TABS} value={tab} onChange={setTab} />
        <div className="flex flex-wrap items-center gap-2">
          <Input
            className="min-w-0 flex-1"
            type="search"
            aria-label="Search the vocabulary"
            placeholder={tab === 'ingredients' ? 'Search ingredients' : 'Search tags'}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Button
            variant="primary"
            onClick={() => {
              setFormError(null)
              setForm({ kind: tab === 'ingredients' ? 'ingredient' : 'tag', row: null })
            }}
          >
            {tab === 'ingredients' ? 'New ingredient' : 'New tag'}
          </Button>
        </div>
      </div>

      {form?.kind === 'ingredient' && (
        <Card>
          <SystemIngredientForm
            key={form.row?.id ?? 'new'}
            ingredient={form.row}
            heading={form.row ? `Edit ${form.row.name}` : 'New ingredient'}
            submitLabel={form.row ? 'Save ingredient' : 'Create ingredient'}
            busy={busy}
            error={formError}
            onSubmit={saveIngredient}
            onCancel={closeForm}
          />
        </Card>
      )}

      {form?.kind === 'tag' && (
        <Card>
          <TagForm key={form.row?.id ?? 'new'} tag={form.row} busy={busy} error={formError} onSubmit={saveTag} onCancel={closeForm} />
        </Card>
      )}

      {failed ? (
        <CatalogLoadFailed message="Couldn't load the system vocabulary." onRetry={reload} />
      ) : tab === 'ingredients' ? (
        <VocabularyList
          name="System ingredients"
          rows={shownIngredients}
          empty={query ? 'No ingredient matches that.' : 'The library has no ingredients yet.'}
          secondaryOf={ingredientMeta}
          badgesOf={(row) => row.categories || []}
          onEdit={(row) => {
            setFormError(null)
            setForm({ kind: 'ingredient', row })
          }}
          onDelete={(row) => askDelete('ingredient', row)}
        />
      ) : (
        <VocabularyList
          name="System tags"
          rows={shownTags}
          empty={query ? 'No tag matches that.' : 'The library has no tags yet.'}
          secondaryOf={(row) =>
            row.penalize_repetition
              ? 'Penalizes repetition: the planner spaces these recipes out'
              : 'Repeats freely'
          }
          badgesOf={() => []}
          onEdit={(row) => {
            setFormError(null)
            setForm({ kind: 'tag', row })
          }}
          onDelete={(row) => askDelete('tag', row)}
        />
      )}

      {notice && <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)} />}

      {pendingDelete && (
        <ConfirmModal
          title={`Delete ${pendingDelete.row.name}?`}
          message={
            pendingDelete.kind === 'ingredient'
              ? `“${pendingDelete.row.name}” is used by ${uses(pendingDelete.count)} in the library. ` +
                'An ingredient a recipe still uses cannot be deleted.'
              : `“${pendingDelete.row.name}” is on ${uses(pendingDelete.count)} in the library. ` +
                'Deleting it removes the tag from them; the recipes stay.'
          }
          confirmLabel={pendingDelete.kind === 'ingredient' ? 'Delete ingredient' : 'Delete tag'}
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  )
}

/**
 * One vocabulary list. There is no table primitive, so this is the hand-rolled
 * `ul` inside a flush `Card` the catalog admin listing already uses.
 *
 * `rows` is null until the first load lands.
 */
function VocabularyList({ name, rows, empty, secondaryOf, badgesOf, onEdit, onDelete }) {
  const headingId = React.useId()

  return (
    <section className="flex flex-col gap-3">
      <h2 id={headingId} style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>
        {name}
      </h2>

      {rows === null && <p style={mutedTextStyle}>Loading the vocabulary…</p>}
      {rows !== null && rows.length === 0 && <p style={mutedTextStyle}>{empty}</p>}

      {rows !== null && rows.length > 0 && (
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
                    }}
                  >
                    {row.name}
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                    {secondaryOf(row)}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1">
                  {badgesOf(row).map((badge) => (
                    <Badge key={badge} tone="sage">
                      {badge}
                    </Badge>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="ghost" onClick={() => onEdit(row)}>
                    Edit
                  </Button>
                  <Button variant="ghost" onClick={() => onDelete(row)}>
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  )
}

/**
 * A system tag is a name and one planner flag, so its form stays here rather
 * than becoming a component: nothing else raises it.
 *
 * `onSubmit` is handed the whole tag when creating and only the changed fields
 * when editing, exactly like `SystemIngredientForm`, because the `PUT` behind
 * it is partial.
 */
function TagForm({ tag = null, busy = false, error = null, onSubmit, onCancel }) {
  const id = React.useId()
  const [name, setName] = React.useState(tag?.name ?? '')
  const [penalize, setPenalize] = React.useState(Boolean(tag?.penalize_repetition))
  const [problem, setProblem] = React.useState(null)

  const submit = (event) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setProblem('A tag needs a name.')
      return
    }
    setProblem(null)
    if (!tag) {
      onSubmit({ name: trimmed, penalize_repetition: penalize })
      return
    }
    const changes = {}
    if (trimmed !== tag.name) changes.name = trimmed
    if (penalize !== Boolean(tag.penalize_repetition)) changes.penalize_repetition = penalize
    onSubmit(changes)
  }

  const shown = problem || error

  return (
    <form className="flex flex-col gap-3" onSubmit={submit}>
      <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>
        {tag ? `Edit ${tag.name}` : 'New tag'}
      </h3>

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-name`} style={mutedTextStyle}>
          Tag name
        </label>
        <Input id={`${id}-name`} value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" />
      </div>

      <label className="flex items-center gap-2" style={{ fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }}>
        <input type="checkbox" checked={penalize} onChange={(event) => setPenalize(event.target.checked)} />
        Penalizes repetition
      </label>

      {shown && (
        <p role="alert" style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-neg)' }}>
          {shown}
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={busy}>
          {tag ? 'Save tag' : 'Create tag'}
        </Button>
      </div>
    </form>
  )
}
