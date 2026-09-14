import React from 'react'
import { FunnelIcon, XMarkIcon } from '@heroicons/react/24/outline'
import {
  ActiveFilterChips,
  Badge,
  BottomSheet,
  Button,
  CatalogRecipeCard,
  CatalogRecipeMedia,
  Icon,
  IconButton,
  Input,
  Modal,
  RecipeFilters,
  RecipeSort,
} from '../components'
import Quantity from '../components/Quantity'
import NewRecipeModal from '../components/NewRecipeModal'
import CatalogAdminListing from '../components/catalog/CatalogAdminListing'
import CatalogAdminToolbar from '../components/catalog/CatalogAdminToolbar'
import { apiErrorText, catalogApi, recipeWriteProblem, toRecipeForm } from '../api/catalogApi'
import { useOptionalAuth } from '../auth/AuthContext'
import { tagsApi } from '../api/tagsApi'
import { COURSES } from '../constants/recipeImport'
import { courseColor, dishIcon } from '../constants/recipeIcons'
import { basisOf, peopleLabel } from '../utils/servings'
import { useEscapeKey } from '../hooks/useEscapeKey'
import { useIsMobile } from '../hooks/useIsMobile'
import { useUnitSystem } from '../hooks/useUnitSystem'

// The catalog's two server-side orderings (API-1). Each has one fixed
// direction, so the sort control shows no direction arrow.
const CATALOG_SORT_OPTIONS = [
  { value: 'popular', label: 'Most added' },
  { value: 'title', label: 'Title' },
]

// Long enough that typing a word issues one request, short enough to feel live.
const SEARCH_DEBOUNCE_MS = 300

const sectionHeadingStyle = {
  fontSize: 'var(--text-sm)',
  fontWeight: 'var(--weight-semibold)',
  marginBottom: 6,
  color: 'var(--text-strong)',
}

const mutedTextStyle = { margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-subtle)' }

const recipesLabel = (n) => `${n} ${n === 1 ? 'recipe' : 'recipes'}`

// Ends a reason with exactly one full stop, whether or not it came with one.
const asSentence = (text) => `${String(text).replace(/\.+$/, '')}.`

const toggleIn = (list, value) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

// The export is a pack-file superset (EXP-4), so it is saved as a JSON file.
function downloadJson(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  try {
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(url)
  }
}

/**
 * The detail view of one catalog recipe: everything needed to decide (UI-7).
 *
 * `onEdit` / `onRetire` are passed for an admin only, and receive the full
 * detail row -- procedure and ingredients included -- so the edit form starts
 * from the whole recipe, not the listing's summary.
 */
function CatalogRecipeDetail({ recipe, onClose, onEdit, onRetire }) {
  const unitSystem = useUnitSystem()
  const [detail, setDetail] = React.useState(null)
  const [failed, setFailed] = React.useState(false)

  // Keyed by the parent on the recipe id, so this state starts fresh per recipe.
  React.useEffect(() => {
    let stale = false
    catalogApi
      .get(recipe.id)
      .then((row) => !stale && setDetail(row))
      .catch((err) => {
        console.error('Failed to load catalog recipe', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [recipe.id])

  // The listing row renders at once; the detail fills in ingredients and procedure.
  const shown = detail || recipe
  const servings = basisOf(shown.servings)

  return (
    <Modal title={shown.title} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <div style={{ position: 'relative', width: '100%', aspectRatio: '16 / 9', overflow: 'hidden' }}>
          <CatalogRecipeMedia recipe={shown} rounded="var(--radius-md)" />
        </div>
        <div
          className="flex items-center gap-1.5"
          style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}
        >
          <Icon set="mdi" name={dishIcon(shown)} size={16} color={courseColor[shown.course] || 'var(--c-a3)'} />
          {shown.course}
        </div>
        {(shown.bulk_prep || (shown.tags || []).length > 0) && (
          <div className="flex flex-wrap gap-1.5">
            {shown.bulk_prep && (
              <Badge tone="gold">
                <img src="/assets/icons/bulk_icon.png" alt="" style={{ height: 12 }} />
                bulk
              </Badge>
            )}
            {(shown.tags || []).map((tag) => (
              <Badge key={tag} tone="caramel">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        {failed && (
          <p role="alert" style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>
            Couldn&apos;t load this recipe. Close it and try again.
          </p>
        )}
        {!detail && !failed && <p style={mutedTextStyle}>Loading…</p>}
        {detail && (
          <div>
            <div style={sectionHeadingStyle}>
              Ingredients for {servings} {peopleLabel(servings)}
            </div>
            <ul style={{ margin: '0 0 12px', paddingLeft: 18, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
              {(detail.ingredients || []).map((ing, i) => (
                <li key={`${ing.name}-${i}`}>
                  <Quantity amount={ing.quantity} unit={ing.unit} system={unitSystem} /> {ing.name}
                </li>
              ))}
            </ul>
            {detail.procedure && (
              <>
                <div style={sectionHeadingStyle}>Procedure</div>
                <p style={{ margin: 0, whiteSpace: 'pre-line', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                  {detail.procedure}
                </p>
              </>
            )}
          </div>
        )}
        {detail && (onEdit || onRetire) && (
          <div className="flex flex-wrap justify-end gap-2 pt-2">
            {onRetire && (
              <Button variant="ghost" onClick={() => onRetire(detail)}>
                Retire
              </Button>
            )}
            {onEdit && (
              <Button variant="secondary" onClick={() => onEdit(detail)}>
                Edit
              </Button>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

/**
 * Discover: browse the system recipe catalog and add recipes to your book.
 *
 * Filtering, search and sort all happen on the server (API-1): every change
 * issues a fresh `catalogApi.list`, with the search debounced. Adding is one
 * batch `catalogApi.adopt` for the whole selection (ADO-5).
 *
 * An admin (`is_admin` on the account) also gets the curation controls
 * (UI-12); for anyone else they are not rendered at all (UI-11). The server
 * enforces the same line with a 403, so this only decides what is shown.
 */
export default function DiscoverPage() {
  const isMobile = useIsMobile()
  const isAdmin = useOptionalAuth()?.user?.is_admin === true

  const [rows, setRows] = React.useState([])
  const [loaded, setLoaded] = React.useState(false)
  const [loadFailed, setLoadFailed] = React.useState(false)
  const [reloadKey, setReloadKey] = React.useState(0)

  const [tagOptions, setTagOptions] = React.useState([])
  const [selectedCourses, setSelectedCourses] = React.useState([])
  const [selectedTags, setSelectedTags] = React.useState([])
  const [search, setSearch] = React.useState('')
  const [query, setQuery] = React.useState('')
  const [sort, setSort] = React.useState('popular')
  const [showFilters, setShowFilters] = React.useState(false)

  const [selectedIds, setSelectedIds] = React.useState([])
  const [adding, setAdding] = React.useState(false)
  // { kind: 'status' | 'alert', text } -- the role doubles as the kind.
  const [notice, setNotice] = React.useState(null)
  const [opened, setOpened] = React.useState(null)

  // Admin only. `showRetired` swaps the browse grid for the admin listing,
  // which has its own request and its own rows (UI-16).
  const [showRetired, setShowRetired] = React.useState(false)
  const [adminRows, setAdminRows] = React.useState(null)
  const [adminReloadKey, setAdminReloadKey] = React.useState(0)
  const [exporting, setExporting] = React.useState(false)
  // The open recipe form: { id (null to create), initialRecipe, error }.
  const [form, setForm] = React.useState(null)

  // Only the system account's tags can appear on a catalog recipe, so the
  // user's own tags would be filters that can never match.
  React.useEffect(() => {
    tagsApi
      .fetchAll()
      .then((tags) => setTagOptions(tags.filter((t) => t.is_system).map((t) => t.name)))
      .catch((err) => console.error('Failed to load tags', err))
  }, [])

  React.useEffect(() => {
    const timer = setTimeout(() => setQuery(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [search])

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    catalogApi
      .list({ courses: selectedCourses, tags: selectedTags, q: query, sort })
      .then((result) => {
        if (stale) return
        setRows(result)
        setLoadFailed(false)
      })
      .catch((err) => {
        console.error('Failed to load the recipe library', err)
        if (!stale) setLoadFailed(true)
      })
      .finally(() => {
        if (!stale) setLoaded(true)
      })
    return () => {
      stale = true
    }
  }, [selectedCourses, selectedTags, query, sort, reloadKey])

  React.useEffect(() => {
    if (!isAdmin || !showRetired) return undefined
    let stale = false
    catalogApi.admin
      .list()
      .then((result) => !stale && setAdminRows(result))
      .catch((err) => {
        console.error('Failed to load the admin catalog listing', err)
        if (!stale) {
          setNotice({ kind: 'alert', text: `Couldn't load the retired entries: ${asSentence(apiErrorText(err))}` })
        }
      })
    return () => {
      stale = true
    }
  }, [isAdmin, showRetired, adminReloadKey])

  // A curation change can move a recipe in or out of either listing.
  const refreshListings = () => {
    setReloadKey((k) => k + 1)
    setAdminReloadKey((k) => k + 1)
  }

  // The form closes as soon as it hands the recipe over, without awaiting
  // this, so a problem reopens it -- with what was typed and the reason --
  // rather than losing the recipe. A slip the server would reject is caught
  // here first, so it never costs a request.
  const saveRecipe = async (recipe) => {
    const { id } = form
    const reopen = (reason) =>
      setForm({ id, initialRecipe: recipe, error: `Couldn't save “${recipe.title}”: ${asSentence(reason)}` })
    setNotice(null)
    const problem = recipeWriteProblem(recipe)
    if (problem) {
      reopen(problem)
      return
    }
    try {
      if (id == null) await catalogApi.admin.create(recipe)
      else await catalogApi.admin.update(id, recipe)
      setNotice({ kind: 'status', text: `Saved “${recipe.title}” to the library.` })
      refreshListings()
    } catch (err) {
      console.error('Failed to save the catalog recipe', err)
      reopen(apiErrorText(err))
    }
  }

  // Closes the form it was rendered for, and only that one: the modal calls
  // this straight after `onSave`, which may already have reopened the form
  // with a problem that must stay on screen.
  const closeForm = (closing) => setForm((current) => (current === closing ? null : current))

  // `action` is 'publish' or 'retire', which is also the endpoint's name.
  const changeStatus = async (action, recipe) => {
    setNotice(null)
    try {
      await catalogApi.admin[action](recipe.id)
      const done = action === 'publish' ? 'Published' : 'Retired'
      setNotice({ kind: 'status', text: `${done} “${recipe.title}”.` })
      refreshListings()
    } catch (err) {
      console.error(`Failed to ${action} the catalog recipe`, err)
      setNotice({ kind: 'alert', text: `Couldn't ${action} “${recipe.title}”: ${asSentence(apiErrorText(err))}` })
    }
  }

  const exportCatalog = async () => {
    setExporting(true)
    setNotice(null)
    try {
      const entries = await catalogApi.admin.exportCatalog()
      downloadJson(entries, `catalog-export-${new Date().toISOString().slice(0, 10)}.json`)
    } catch (err) {
      console.error('Failed to export the catalog', err)
      setNotice({ kind: 'alert', text: `Couldn't export the library: ${asSentence(apiErrorText(err))}` })
    } finally {
      setExporting(false)
    }
  }

  const editRecipe = (recipe) => {
    setOpened(null)
    setForm({ id: recipe.id, initialRecipe: toRecipeForm(recipe), error: null })
  }

  const retireFromDetail = (recipe) => {
    setOpened(null)
    changeStatus('retire', recipe)
  }

  const managing = isAdmin && showRetired

  // One list drives the popover, the sheet and the active-filter chips, as on
  // the Recipes page, so the three surfaces cannot drift apart.
  const filterGroups = React.useMemo(
    () => [
      {
        label: 'Course',
        options: COURSES,
        selected: selectedCourses,
        onSelect: (course) => setSelectedCourses((cs) => toggleIn(cs, course)),
        clear: () => setSelectedCourses([]),
      },
      {
        label: 'Tags',
        options: tagOptions,
        selected: selectedTags,
        onSelect: (tag) => setSelectedTags((ts) => toggleIn(ts, tag)),
        clear: () => setSelectedTags([]),
      },
    ],
    [selectedCourses, selectedTags, tagOptions],
  )

  const activeFilters = React.useMemo(
    () =>
      filterGroups.flatMap(({ selected, onSelect }) =>
        selected.map((value) => ({ value, onRemove: () => onSelect(value) })),
      ),
    [filterGroups],
  )

  const clearAllFilters = () => filterGroups.forEach((group) => group.clear())

  const clearSearchAndFilters = () => {
    setSearch('')
    // Skip the debounce: the user asked for everything back, not for a search.
    setQuery('')
    clearAllFilters()
  }

  // The desktop popover dismisses on Escape and outside click; the sheet
  // handles its own Escape.
  const filterRef = React.useRef(null)
  const closeFilters = React.useCallback(() => setShowFilters(false), [])
  useEscapeKey(showFilters && !isMobile, closeFilters)
  React.useEffect(() => {
    if (!showFilters || isMobile) return undefined
    const onDown = (e) => {
      if (filterRef.current && !filterRef.current.contains(e.target)) setShowFilters(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [showFilters, isMobile])

  // Locked while adding: a tick landing mid-request would be wiped by the
  // success path and would clear the in-flight notice (UI-8/UI-15).
  const toggleSelected = (id) => {
    if (adding) return
    setNotice(null)
    setSelectedIds((ids) => toggleIn(ids, id))
  }

  // Held cards have no checkbox (UI-9), so everything selected is something the
  // server will create: the button's count is the number added (UI-8).
  const addSelected = async () => {
    setAdding(true)
    setNotice(null)
    try {
      const { created_ids: created = [], skipped_ids: skipped = [] } = await catalogApi.adopt(selectedIds)
      const already = skipped.length > 0 ? ` ${recipesLabel(skipped.length)} already there.` : ''
      setNotice({ kind: 'status', text: `Added ${recipesLabel(created.length)} to your book.${already}` })
      setSelectedIds([])
      setReloadKey((k) => k + 1)
    } catch (err) {
      console.error('Failed to add catalog recipes', err)
      // UI-15: say what failed, and keep the selection so a retry is one tap.
      setNotice({
        kind: 'alert',
        text: `Couldn't add ${recipesLabel(selectedIds.length)}: ${err.message}. Your selection is kept, so you can try again.`,
      })
    } finally {
      setAdding(false)
    }
  }

  const filtering = activeFilters.length > 0 || query.trim() !== ''

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>Discover</h1>
          <p style={{ ...mutedTextStyle, marginTop: 4 }}>
            Recipes from the Meal Planner library. Pick the ones you like and add them to your book.
          </p>
        </div>
        {/* Browsing controls; the admin listing is unfiltered, so they would do nothing there. */}
        {!managing && (
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <div className="relative" ref={filterRef}>
              <Button
                variant="ghost"
                aria-label="Filter"
                className="relative"
                onClick={() => setShowFilters((s) => !s)}
                Icon={FunnelIcon}
              >
                {activeFilters.length > 0 && (
                  <span
                    className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs"
                    style={{ backgroundColor: 'var(--c-neg)', color: '#fff' }}
                  >
                    {activeFilters.length}
                  </span>
                )}
              </Button>
              {showFilters && !isMobile && (
                <div
                  className="absolute left-0 z-10 mt-2 w-[min(20rem,calc(100vw-2rem))] rounded-2xl border bg-white p-2 md:left-auto md:right-0"
                  style={{ borderColor: 'var(--border-default)' }}
                >
                  <RecipeFilters groups={filterGroups} />
                </div>
              )}
            </div>
            <Input
              placeholder="Search the library…"
              aria-label="Search the library"
              className="min-w-0 flex-1 md:w-56 md:flex-none"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <RecipeSort
              sortKey={sort}
              options={CATALOG_SORT_OPTIONS}
              showDirection={false}
              onChange={(key) => setSort(key)}
            />
          </div>
        )}
      </div>

      {isAdmin && (
        <CatalogAdminToolbar
          showRetired={showRetired}
          exporting={exporting}
          onNew={() => setForm({ id: null, initialRecipe: undefined, error: null })}
          onToggleRetired={() => setShowRetired((on) => !on)}
          onExport={exportCatalog}
        />
      )}

      {managing ? (
        <CatalogAdminListing
          rows={adminRows}
          onEdit={editRecipe}
          onPublish={(recipe) => changeStatus('publish', recipe)}
          onRetire={(recipe) => changeStatus('retire', recipe)}
        />
      ) : (
        <>
          <ActiveFilterChips filters={activeFilters} onClearAll={clearAllFilters} />

          {!loaded && <p style={mutedTextStyle}>Loading the recipe library…</p>}

          {loadFailed && (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p role="alert" style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>
                Couldn&apos;t load the recipe library.
              </p>
              <Button variant="ghost" onClick={() => setReloadKey((k) => k + 1)}>
                Try again
              </Button>
            </div>
          )}

          {loaded && !loadFailed && rows.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p style={mutedTextStyle}>
                {filtering ? 'No recipes match your search.' : 'The recipe library is empty right now. Check back soon.'}
              </p>
              {filtering && (
                <Button variant="ghost" onClick={clearSearchAndFilters}>
                  Clear search and filters
                </Button>
              )}
            </div>
          )}

          {!loadFailed && rows.length > 0 && (
            <div className="card-grid">
              {rows.map((recipe) => (
                <CatalogRecipeCard
                  key={recipe.id}
                  recipe={recipe}
                  selected={selectedIds.includes(recipe.id)}
                  disabled={adding}
                  onToggle={() => toggleSelected(recipe.id)}
                  onOpen={() => setOpened(recipe)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {(selectedIds.length > 0 || notice) && (
        // In the flow rather than fixed, so it never covers the last row of cards.
        <div
          className="sticky bottom-0 z-10 flex flex-wrap items-center gap-2 border bg-white p-3"
          style={{
            borderColor: 'var(--border-default)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-md)',
            marginBottom: 'env(safe-area-inset-bottom)',
          }}
        >
          {notice && (
            <p
              role={notice.kind}
              className="min-w-0 flex-1"
              style={{
                margin: 0,
                fontSize: 'var(--text-sm)',
                color: notice.kind === 'alert' ? 'var(--c-neg)' : 'var(--text-strong)',
              }}
            >
              {notice.text}
            </p>
          )}
          {selectedIds.length > 0 ? (
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Button variant="ghost" disabled={adding} onClick={() => setSelectedIds([])}>
                Clear selection
              </Button>
              <Button variant="accent" disabled={adding} onClick={addSelected}>
                {adding ? 'Adding…' : `Add ${recipesLabel(selectedIds.length)}`}
              </Button>
            </div>
          ) : (
            <IconButton Icon={XMarkIcon} label="Dismiss" className="ml-auto" onClick={() => setNotice(null)} />
          )}
        </div>
      )}

      {opened && (
        <CatalogRecipeDetail
          key={opened.id}
          recipe={opened}
          onClose={() => setOpened(null)}
          onEdit={isAdmin ? editRecipe : undefined}
          onRetire={isAdmin ? retireFromDetail : undefined}
        />
      )}

      {form && (
        // Catalog mode (plan D3): the library's own ingredients and tags, and no
        // new names -- the server rejects any name the library lacks. Image
        // upload stays on: `/recipes/upload-image` is plain storage, not tied
        // to a recipe or its owner.
        <NewRecipeModal
          heading={form.id == null ? 'New catalog recipe' : 'Edit catalog recipe'}
          initialRecipe={form.initialRecipe}
          loadIngredients={catalogApi.admin.ingredients}
          loadTags={catalogApi.admin.tags}
          allowCreateIngredient={false}
          allowCreateTag={false}
          notice={
            form.error && (
              <p role="alert" className="text-sm" style={{ margin: 0, color: 'var(--c-neg)' }}>
                {form.error}
              </p>
            )
          }
          onSave={saveRecipe}
          onClose={() => closeForm(form)}
        />
      )}

      {showFilters && isMobile && (
        <BottomSheet
          title="Filters"
          onClose={closeFilters}
          footer={
            <Button variant="accent" className="w-full" onClick={closeFilters}>
              {`Show ${recipesLabel(rows.length)}`}
            </Button>
          }
        >
          <RecipeFilters groups={filterGroups} />
        </BottomSheet>
      )}
    </div>
  )
}
