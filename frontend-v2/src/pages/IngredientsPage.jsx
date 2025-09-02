import React from 'react'
import {
  Input,
  MonthFilter,
  IngredientCard,
  EditIngredientModal,
  ConfirmIngredientChangeModal,
} from '../components'
import { ingredientsApi } from '../api/ingredientsApi'

export default function IngredientsPage() {
  const [query, setQuery] = React.useState('')
  const [selectedMonths, setSelectedMonths] = React.useState([])
  const [mode, setMode] = React.useState('any')
  const [ingredients, setIngredients] = React.useState([])
  const [expanded, setExpanded] = React.useState(null)
  const [editing, setEditing] = React.useState(null)
  const [confirm, setConfirm] = React.useState(null)

  React.useEffect(() => {
    async function load() {
      try {
        const data = query
          ? await ingredientsApi.search(query)
          : await ingredientsApi.fetchAll()
        setIngredients(data)
      } catch (err) {
        console.error('Failed to load ingredients', err)
      }
    }
    load()
  }, [query])

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
            })
            setIngredients((ings) =>
              ings.map((i) =>
                i.id === editing.id ? { ...i, ...updated } : i
              )
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
      </div>
      <h1 className="text-xl font-medium" style={{ color: 'var(--text-strong)' }}>
        Ingredients
      </h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 items-start">
        {filtered.map((ing) => (
          <IngredientCard
            key={ing.id}
            name={ing.name}
            unit={ing.unit}
            season={ing.season_months || []}
            expanded={expanded === ing.id}
            onToggle={() => setExpanded(expanded === ing.id ? null : ing.id)}
            onEdit={() => handleEdit(ing)}
            onDelete={() => handleDelete(ing.id)}
          />
        ))}
      </div>
      {editing && (
        <EditIngredientModal
          ingredient={editing}
          onClose={() => setEditing(null)}
          onSave={handleSaveEdit}
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

