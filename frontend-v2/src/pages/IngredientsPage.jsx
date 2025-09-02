import React from 'react'
import { Input, MonthFilter, IngredientCard } from '../components'
import { ingredientsApi } from '../api/ingredientsApi'

export default function IngredientsPage() {
  const [query, setQuery] = React.useState('')
  const [selectedMonths, setSelectedMonths] = React.useState([])
  const [mode, setMode] = React.useState('any')
  const [ingredients, setIngredients] = React.useState([])
  const [expanded, setExpanded] = React.useState(null)

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
      await ingredientsApi.remove(id)
      setIngredients((ings) => ings.filter((i) => i.id !== id))
    } catch (err) {
      console.error('Failed to delete ingredient', err)
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((ing) => (
          <IngredientCard
            key={ing.id}
            name={ing.name}
            unit={ing.unit}
            season={ing.season_months || []}
            expanded={expanded === ing.id}
            onToggle={() => setExpanded(expanded === ing.id ? null : ing.id)}
            onEdit={() => console.log('edit ingredient', ing.id)}
            onDelete={() => handleDelete(ing.id)}
          />
        ))}
      </div>
    </div>
  )
}

