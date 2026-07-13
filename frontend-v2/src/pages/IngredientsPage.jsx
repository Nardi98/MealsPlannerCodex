import React from 'react'
import {
  Input,
  MonthFilter,
  IngredientCard,
  EditIngredientModal,
  ConfirmIngredientChangeModal,
  AddIngredientModal,
  MergeIngredientsModal,
  ToggleChip,
  Button,
} from '../components'
import { ingredientsApi } from '../api/ingredientsApi'
import { groupByCategory } from '../utils/groupIngredients'

const COLLAPSE_KEY = 'ingredientSectionCollapsed'

function readCollapsed() {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') || {}
  } catch {
    return {}
  }
}

export default function IngredientsPage() {
  const [query, setQuery] = React.useState('')
  const [selectedMonths, setSelectedMonths] = React.useState([])
  const [mode, setMode] = React.useState('any')
  const [ingredients, setIngredients] = React.useState([])
  const [expanded, setExpanded] = React.useState(null)
  const [editing, setEditing] = React.useState(null)
  const [confirm, setConfirm] = React.useState(null)
  const [adding, setAdding] = React.useState(false)
  const [merging, setMerging] = React.useState(false)
  const [selectedCategories, setSelectedCategories] = React.useState(null)
  const [collapsed, setCollapsed] = React.useState(readCollapsed)

  const load = React.useCallback(async () => {
    try {
      const data = query
        ? await ingredientsApi.search(query)
        : await ingredientsApi.fetchAll()
      setIngredients(data)
    } catch (err) {
      console.error('Failed to load ingredients', err)
    }
  }, [query])

  React.useEffect(() => {
    load()
  }, [load])

  const filtered = React.useMemo(() => {
    if (!selectedMonths.length) return ingredients
    return ingredients.filter((ing) => {
      const months = ing.season_months || []
      if (mode === 'all') {
        return selectedMonths.every((m) => months.includes(m))
      }
      return selectedMonths.some((m) => months.includes(m))
    })
  }, [ingredients, selectedMonths, mode])

  // Non-empty groups in canonical order.
  const groups = React.useMemo(
    () => groupByCategory(filtered).filter((g) => g.items.length > 0),
    [filtered]
  )

  // Initialise pill selection to ALL present categories whenever the set of
  // present categories changes (not persisted; resets each visit).
  const presentKey = groups.map((g) => g.category).join('|')
  React.useEffect(() => {
    setSelectedCategories(new Set(groups.map((g) => g.category)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presentKey])

  const togglePill = (category) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(category)) next.delete(category)
      else next.add(category)
      return next
    })
  }

  const toggleCollapse = (category) => {
    setCollapsed((prev) => {
      const next = { ...prev, [category]: !prev[category] }
      try {
        localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next))
      } catch {
        /* ignore storage errors */
      }
      return next
    })
  }

  const handleDelete = async (id) => {
    try {
      const recipes = await ingredientsApi.recipes(id)
      setConfirm({
        action: 'delete',
        recipes,
        onConfirm: async () => {
          try {
            await ingredientsApi.remove(id, true)
            setIngredients((ings) => ings.filter((i) => i.id !== id))
          } catch (err) {
            console.error('Failed to delete ingredient', err)
          } finally {
            setConfirm(null)
          }
        },
      })
    } catch (err) {
      console.error('Failed to load recipes', err)
    }
  }

  const handleEdit = (ing) => setEditing(ing)
  const handleSaveEdit = async (updates) => {
    try {
      const recipes = await ingredientsApi.recipes(editing.id)
      setConfirm({
        action: 'edit',
        recipes,
        onConfirm: async () => {
          try {
            const updated = await ingredientsApi.update(editing.id, {
              name: updates.name,
              unit: updates.unit,
              season_months: updates.season,
              categories: updates.categories,
            })
            setIngredients((ings) =>
              ings.map((i) => (i.id === editing.id ? { ...i, ...updated } : i))
            )
            setEditing(null)
          } catch (err) {
            console.error('Failed to update ingredient', err)
          } finally {
            setConfirm(null)
          }
        },
      })
    } catch (err) {
      console.error('Failed to load recipes', err)
    }
  }

  const handleAdd = async ({ name, unit, season, categories }) => {
    try {
      const created = await ingredientsApi.create({
        name,
        unit,
        season_months: season,
        categories,
      })
      setIngredients((ings) =>
        !query || created.name.toLowerCase().includes(query.toLowerCase())
          ? [...ings, created]
          : ings
      )
    } catch (err) {
      console.error('Failed to add ingredient', err)
      alert('Failed to add ingredient')
      throw err
    }
  }

  const selected = selectedCategories || new Set()

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search ingredients…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-56"
        />
        <MonthFilter
          selectedMonths={selectedMonths}
          onMonthsChange={setSelectedMonths}
          mode={mode}
          onModeChange={setMode}
        />
        <Button variant="a1" onClick={() => setAdding(true)}>
          + New ingredient
        </Button>
        <Button variant="a2" onClick={() => setMerging(true)}>
          Merge ingredients
        </Button>
      </div>
      <h1 className="text-xl font-medium" style={{ color: 'var(--text-strong)' }}>
        Ingredients
      </h1>

      {/* Category pills */}
      <div className="flex flex-wrap gap-1.5">
        {groups.map((g) => (
          <ToggleChip
            key={g.category}
            active={selected.has(g.category)}
            onClick={() => togglePill(g.category)}
            label={`${g.category} filter`}
          >
            {g.category} · {g.items.length}
          </ToggleChip>
        ))}
      </div>

      {/* Sections */}
      <div className="space-y-4">
        {groups
          .filter((g) => selected.has(g.category))
          .map((g) => {
            const isCollapsed = !!collapsed[g.category]
            return (
              <section key={g.category}>
                <button
                  type="button"
                  onClick={() => toggleCollapse(g.category)}
                  aria-label={`${g.category} section`}
                  className="flex items-center gap-2 w-full text-left py-1"
                  style={{ color: 'var(--text-strong)' }}
                >
                  <span className="text-xs">{isCollapsed ? '▸' : '▾'}</span>
                  <span className="font-medium">{g.category}</span>
                  <span className="text-xs text-[color:var(--text-subtle)]">
                    · {g.items.length}
                  </span>
                </button>
                {!isCollapsed && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 items-start mt-2">
                    {g.items.map((ing) => (
                      <IngredientCard
                        key={`${g.category}-${ing.id}`}
                        name={ing.name}
                        unit={ing.unit}
                        season={ing.season_months || []}
                        categories={ing.categories || []}
                        expanded={expanded === `${g.category}-${ing.id}`}
                        onToggle={() =>
                          setExpanded(
                            expanded === `${g.category}-${ing.id}`
                              ? null
                              : `${g.category}-${ing.id}`
                          )
                        }
                        onEdit={() => handleEdit(ing)}
                        onDelete={() => handleDelete(ing.id)}
                      />
                    ))}
                  </div>
                )}
              </section>
            )
          })}
      </div>

      {editing && (
        <EditIngredientModal
          ingredient={editing}
          onClose={() => setEditing(null)}
          onSave={handleSaveEdit}
        />
      )}
      {adding && (
        <AddIngredientModal
          onClose={() => setAdding(false)}
          onSave={handleAdd}
        />
      )}
      {merging && (
        <MergeIngredientsModal
          onClose={() => setMerging(false)}
          onMerged={load}
        />
      )}
      {confirm && (
        <ConfirmIngredientChangeModal
          action={confirm.action}
          recipes={confirm.recipes}
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  )
}
