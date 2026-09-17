import React from 'react'
import {
  ActiveFilterChips,
  Button,
  CatalogRecipeCard,
  Input,
  RecipeFilterControl,
  RecipeSort,
} from '../components'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import CatalogRecipeDetail from '../components/catalog/CatalogRecipeDetail'
import { mutedTextStyle } from '../components/catalog/textStyles'
import { catalogApi } from '../api/catalogApi'
import { tagsApi } from '../api/tagsApi'
import { CATALOG_SORT_OPTIONS } from '../constants/catalog'
import { COURSES } from '../constants/recipeImport'
import { useDebounced } from '../hooks/useDebounced'
import { toggleIn } from '../utils/toggleIn'

const recipesLabel = (n) => `${n} ${n === 1 ? 'recipe' : 'recipes'}`

/**
 * Discover: browse the system recipe catalog and add recipes to your book.
 *
 * Filtering, search and sort all happen on the server (API-1): every change
 * issues a fresh `catalogApi.list`, with the search debounced. Adding is one
 * batch `catalogApi.adopt` for the whole selection (ADO-5).
 *
 * Curation lives elsewhere: an admin switches to admin mode and gets
 * `CatalogAdminPage` at this same route (UI-11/UI-12). Nothing on this page
 * changes for an admin, so there is no state in which a user's screen and an
 * admin's screen are the same screen wearing extra buttons.
 */
export default function DiscoverPage() {
  const [rows, setRows] = React.useState([])
  // The latest settled listing request: 'loading' | 'ready' | 'failed'. Only
  // the first request shows 'loading'; a refetch keeps what is on screen --
  // stale rows, or the error with its retry -- until it settles.
  const [status, setStatus] = React.useState('loading')
  const [reloadKey, setReloadKey] = React.useState(0)

  const [tagOptions, setTagOptions] = React.useState([])
  const [selectedCourses, setSelectedCourses] = React.useState([])
  const [selectedTags, setSelectedTags] = React.useState([])
  const [search, setSearch] = React.useState('')
  const query = useDebounced(search.trim())
  const [sort, setSort] = React.useState('popular')

  const [selectedIds, setSelectedIds] = React.useState([])
  const [adding, setAdding] = React.useState(false)
  // { kind: 'status' | 'alert', text } -- the role doubles as the kind.
  const [notice, setNotice] = React.useState(null)
  const [opened, setOpened] = React.useState(null)

  // Only the system account's tags can appear on a catalog recipe, so the
  // user's own tags would be filters that can never match.
  React.useEffect(() => {
    tagsApi
      .fetchAll()
      .then((tags) => setTagOptions(tags.filter((t) => t.is_system).map((t) => t.name)))
      .catch((err) => console.error('Failed to load tags', err))
  }, [])

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    catalogApi
      .list({ courses: selectedCourses, tags: selectedTags, q: query, sort })
      .then((result) => {
        if (stale) return
        setRows(result)
        setStatus('ready')
      })
      .catch((err) => {
        console.error('Failed to load the recipe library', err)
        if (!stale) setStatus('failed')
      })
    return () => {
      stale = true
    }
  }, [selectedCourses, selectedTags, query, sort, reloadKey])

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
    clearAllFilters()
  }

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

  const filtering = activeFilters.length > 0 || query !== ''

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>Discover</h1>
          <p style={{ ...mutedTextStyle, marginTop: 4 }}>
            Recipes from the Meal Planner library. Pick the ones you like and add them to your book.
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
          <RecipeFilterControl
            groups={filterGroups}
            activeCount={activeFilters.length}
            resultCount={rows.length}
            popoverPosition="left-0 md:left-auto md:right-0"
          />
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
            onChange={setSort}
          />
        </div>
      </div>

      <ActiveFilterChips filters={activeFilters} onClearAll={clearAllFilters} />

      {status === 'loading' && <p style={mutedTextStyle}>Loading the recipe library…</p>}

      {status === 'failed' && (
        <CatalogLoadFailed
          message="Couldn't load the recipe library."
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      )}

      {status === 'ready' && rows.length === 0 && (
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

      {status === 'ready' && rows.length > 0 && (
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

      {(selectedIds.length > 0 || notice) && (
        <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)}>
          {selectedIds.length > 0 && (
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Button variant="ghost" disabled={adding} onClick={() => setSelectedIds([])}>
                Clear selection
              </Button>
              <Button variant="accent" disabled={adding} onClick={addSelected}>
                {adding ? 'Adding…' : `Add ${recipesLabel(selectedIds.length)}`}
              </Button>
            </div>
          )}
        </CatalogNoticeBar>
      )}

      {opened && (
        <CatalogRecipeDetail
          key={opened.id}
          recipe={opened}
          onClose={() => setOpened(null)}
        />
      )}

    </div>
  )
}
