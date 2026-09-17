import React from 'react'
import NewRecipeModal from '../components/NewRecipeModal'
import CatalogAdminListing from '../components/catalog/CatalogAdminListing'
import CatalogAdminToolbar from '../components/catalog/CatalogAdminToolbar'
import CatalogLoadFailed from '../components/catalog/CatalogLoadFailed'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import { mutedTextStyle } from '../components/catalog/textStyles'
import { apiErrorText, catalogApi, recipeWriteProblem, toRecipeForm } from '../api/catalogApi'
import { CATALOG_SORT_OPTIONS } from '../constants/catalog'
import { useDebounced } from '../hooks/useDebounced'
import { downloadJson } from '../utils/download'

// Ends a reason with exactly one full stop, whether or not it came with one.
const asSentence = (text) => `${String(text).replace(/\.+$/, '')}.`

/**
 * The library admin's view of Discover: curate the catalog, don't shop in it.
 *
 * Rendered at `/discover` in admin mode, where `DiscoverPage` is rendered in
 * user mode. The split is the point: this page never adopts, never shows a
 * card and never asks the user-facing endpoints anything, so the two jobs an
 * admin account has cannot be done half-in-each-other's-screen.
 *
 * Every write here is admin-only on the server (403 otherwise); the mode only
 * decides which page is mounted, and is not a permission.
 */
export default function CatalogAdminPage() {
  // null until the first listing lands, which is how `CatalogAdminListing`
  // already reads "still loading". A refetch keeps what is on screen until it
  // settles, so narrowing the list never blanks it.
  const [rows, setRows] = React.useState(null)
  const [failed, setFailed] = React.useState(false)
  const [reloadKey, setReloadKey] = React.useState(0)

  const [search, setSearch] = React.useState('')
  const query = useDebounced(search.trim())
  const [entryStatus, setEntryStatus] = React.useState('')
  const [sort, setSort] = React.useState('title')

  const [exporting, setExporting] = React.useState(false)
  // { kind: 'status' | 'alert', text } -- the role doubles as the kind.
  const [notice, setNotice] = React.useState(null)
  // The open recipe form: { id (null to create), initialRecipe, error }.
  const [form, setForm] = React.useState(null)

  React.useEffect(() => {
    // A slower, older response must not overwrite a newer one.
    let stale = false
    catalogApi.admin
      .list({ q: query, status: entryStatus, sort })
      .then((result) => {
        if (stale) return
        setRows(result)
        setFailed(false)
      })
      .catch((err) => {
        console.error('Failed to load the catalog entries', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [query, entryStatus, sort, reloadKey])

  const refreshListing = () => setReloadKey((k) => k + 1)

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
      refreshListing()
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
      refreshListing()
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
      // The export is a pack-file superset (EXP-4), so it is saved as a JSON file.
      downloadJson(entries, `catalog-export-${new Date().toISOString().slice(0, 10)}.json`)
    } catch (err) {
      console.error('Failed to export the catalog', err)
      setNotice({ kind: 'alert', text: `Couldn't export the library: ${asSentence(apiErrorText(err))}` })
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>Discover</h1>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          The Meal Planner library, as its keeper sees it. Add recipes, edit them, and publish or
          retire what everyone else can find.
        </p>
      </div>

      <CatalogAdminToolbar
        search={search}
        status={entryStatus}
        sort={sort}
        sortOptions={CATALOG_SORT_OPTIONS}
        exporting={exporting}
        onSearch={setSearch}
        onStatus={setEntryStatus}
        onSort={setSort}
        onNew={() => setForm({ id: null, initialRecipe: undefined, error: null })}
        onExport={exportCatalog}
      />

      {failed ? (
        <CatalogLoadFailed message="Couldn't load the library entries." onRetry={refreshListing} />
      ) : (
        <CatalogAdminListing
          rows={rows}
          onEdit={(recipe) => setForm({ id: recipe.id, initialRecipe: toRecipeForm(recipe), error: null })}
          onPublish={(recipe) => changeStatus('publish', recipe)}
          onRetire={(recipe) => changeStatus('retire', recipe)}
        />
      )}

      {notice && <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)} />}

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
    </div>
  )
}
