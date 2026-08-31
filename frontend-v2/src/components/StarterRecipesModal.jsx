import React from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import { Badge } from './Badge'
import { STARTER_RECIPES, groupStarterRecipes } from '../constants/starterRecipes'
import { recipesApi } from '../api/recipesApi'
import { basisOf } from '../utils/servings'

// Offered on the first visit to an empty recipe book (RecipesPage). Everything
// is ticked to begin with: the friction this removes is having to type a first
// recipe, so the default has to be "yes, all of them".

const GROUPS = groupStarterRecipes(STARTER_RECIPES)
const ALL_SLUGS = STARTER_RECIPES.map((recipe) => recipe.slug)

// Match a pack ingredient against a row the account already owns and hand the
// backend that row's id, so the import reuses the seeded ingredient instead of
// creating a near-duplicate. The *line* keeps the unit the pack states -- the
// ingredient no longer owns one, and its conversions (seeded alongside it in
// system_ingredients.json) are what unify the two. A name miss is left to
// `crud.get_or_create_ingredient`, which creates the row under this user --
// the pack's ingredients are all tested to exist, so it should not happen.
function resolveIngredients(recipe, ownedByName) {
  return recipe.ingredients.map((ing) => {
    const owned = ownedByName.get(ing.name.toLowerCase())
    return {
      ...(owned ? { id: owned.id } : {}),
      name: ing.name,
      amount: ing.quantity,
      unit: ing.unit,
    }
  })
}

function Checkbox({ checked, onChange, label, indeterminate = false }) {
  const ref = React.useRef(null)
  React.useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate
  }, [indeterminate])
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={label}
      className="h-4 w-4 flex-shrink-0 cursor-pointer"
      style={{ accentColor: 'var(--c-pos)' }}
    />
  )
}

// `ingredients` are the account's own rows, already loaded by RecipesPage.
export default function StarterRecipesModal({ onClose, onImported, ingredients = [] }) {
  const [selected, setSelected] = React.useState(() => new Set(ALL_SLUGS))
  const [busy, setBusy] = React.useState(false)
  const [done, setDone] = React.useState(0)
  const [failed, setFailed] = React.useState([])

  const ownedByName = React.useMemo(
    () => new Map(ingredients.map((row) => [row.name.toLowerCase(), row])),
    [ingredients],
  )

  const toggle = (slug) => setSelected((prev) => {
    const next = new Set(prev)
    if (next.has(slug)) next.delete(slug)
    else next.add(slug)
    return next
  })

  const setGroup = (group, on) => setSelected((prev) => {
    const next = new Set(prev)
    group.recipes.forEach((r) => (on ? next.add(r.slug) : next.delete(r.slug)))
    return next
  })

  const setAll = (on) => setSelected(on ? new Set(ALL_SLUGS) : new Set())

  async function importSelected() {
    const chosen = STARTER_RECIPES.filter((r) => selected.has(r.slug))
    setBusy(true)
    setFailed([])
    setDone(0)

    const errors = []
    // Sequential on purpose: `crud.get_or_create_ingredient` resolves by name,
    // so parallel creates would race each other into duplicate rows.
    for (const recipe of chosen) {
      try {
        await recipesApi.create({
          title: recipe.title,
          course: recipe.course,
          // The pack's quantities are imported as authored, so the basis they
          // were written for has to come with them. Most entries state none,
          // meaning one person.
          servings: basisOf(recipe.servings),
          hot: recipe.bulk_prep,
          tags: recipe.tags,
          procedure: recipe.procedure,
          ingredients: resolveIngredients(recipe, ownedByName),
        })
        setDone((n) => n + 1)
      } catch {
        errors.push(recipe.slug)
      }
    }

    setBusy(false)
    if (errors.length) {
      // Leave exactly the failures ticked, so the footer button offers a retry
      // of what is left and nothing is created twice.
      setSelected(new Set(errors))
      setFailed(STARTER_RECIPES.filter((r) => errors.includes(r.slug)).map((r) => r.title))
      return
    }
    onImported()
  }

  const count = selected.size

  return (
    <Modal title="Start with a few recipes" onClose={onClose} maxWidth={640}>
      <p style={{ marginTop: -8, marginBottom: 16, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
        Pick the ones you would actually cook — you can edit or delete any of them later.
      </p>

      <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {count} of {STARTER_RECIPES.length} selected
        </span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setAll(true)}>Select all</Button>
          <Button variant="ghost" size="sm" onClick={() => setAll(false)}>Deselect all</Button>
        </div>
      </div>

      {failed.length > 0 && (
        <p role="alert" style={{ marginBottom: 12, fontSize: 'var(--text-sm)', color: 'var(--c-neg)' }}>
          Could not add: {failed.join(', ')}. They are still selected — try again.
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        {GROUPS.map((group) => {
          const chosen = group.recipes.filter((r) => selected.has(r.slug)).length
          const all = chosen === group.recipes.length
          return (
            <section key={group.key}>
              <label className="flex items-center gap-2" style={{ marginBottom: 8, cursor: 'pointer' }}>
                <Checkbox
                  checked={all}
                  indeterminate={chosen > 0 && !all}
                  label={group.label}
                  onChange={() => setGroup(group, !all)}
                />
                <h4
                  style={{
                    margin: 0,
                    fontFamily: 'var(--font-display)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 'var(--weight-semibold)',
                    color: 'var(--text-strong)',
                  }}
                >
                  {group.label}
                </h4>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                  {chosen}/{group.recipes.length}
                </span>
              </label>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 8 }}>
                {group.recipes.map((recipe) => (
                  <label
                    key={recipe.slug}
                    className="flex items-start gap-3"
                    style={{
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-md)',
                      background: selected.has(recipe.slug) ? 'var(--surface-sunken)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <span style={{ paddingTop: 2 }}>
                      <Checkbox
                        checked={selected.has(recipe.slug)}
                        label={recipe.title}
                        onChange={() => toggle(recipe.slug)}
                      />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <span className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
                        <span
                          style={{
                            fontSize: 'var(--text-sm)',
                            fontWeight: 'var(--weight-medium)',
                            color: 'var(--text-strong)',
                          }}
                        >
                          {recipe.title}
                        </span>
                        <Badge>{recipe.minutes} min</Badge>
                      </span>
                      <span
                        style={{ display: 'block', fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}
                      >
                        {recipe.blurb}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </section>
          )
        })}
      </div>

      <div className="flex items-center justify-end gap-2" style={{ marginTop: 20 }}>
        {busy && (
          <span style={{ marginRight: 'auto', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
            Adding… {done} done
          </span>
        )}
        <Button variant="ghost" onClick={onClose} disabled={busy}>Maybe later</Button>
        <Button onClick={importSelected} disabled={busy || count === 0}>
          Add {count} {count === 1 ? 'recipe' : 'recipes'}
        </Button>
      </div>
    </Modal>
  )
}
