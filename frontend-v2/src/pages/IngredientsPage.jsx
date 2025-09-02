import React from 'react'
import { BeakerIcon } from '@heroicons/react/24/outline'
import { Card, Input, MonthFilter, IngredientCard } from '../components'
import { ingredientsApi } from '../api/ingredientsApi'
import { isInSeason, matchesAll } from '../utils/season'

export default function IngredientsPage() {
  const [ingredients, setIngredients] = React.useState([])
  const [query, setQuery] = React.useState('')
  const [selectedMonths, setSelectedMonths] = React.useState([])
  const [mode, setMode] = React.useState('any')

  React.useEffect(() => {
    async function load() {
      try {
        const data = await ingredientsApi.fetchAll()
        setIngredients(data)
      } catch (err) {
        console.error('Failed to load ingredients', err)
      }
    }
    load()
  }, [])

  const filtered = React.useMemo(() => {
    const q = query.toLowerCase()
    return ingredients
      .filter((i) => i.name.toLowerCase().includes(q))
      .filter((i) => {
        const months = i.season || []
        return mode === 'all'
          ? matchesAll(months, selectedMonths)
          : isInSeason(months, selectedMonths)
      })
  }, [ingredients, query, selectedMonths, mode])

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BeakerIcon className="h-5 w-5" /> Ingredients
        </div>
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
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {filtered.map((ing) => (
          <IngredientCard
            key={ing.id}
            name={ing.name}
            unit={ing.unit}
            season={ing.season}
          />
        ))}
      </div>
    </Card>
  )
}

