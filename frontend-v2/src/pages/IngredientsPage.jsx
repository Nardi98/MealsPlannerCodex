import React from 'react'
import { Input, MonthFilter } from '../components'
import { ingredientsApi } from '../api/ingredientsApi'

export default function IngredientsPage() {
  const [query, setQuery] = React.useState('')
  const [selectedMonths, setSelectedMonths] = React.useState([])
  const [mode, setMode] = React.useState('any')

  React.useEffect(() => {
    ingredientsApi.search(query).catch((err) => {
      console.error('Failed to search ingredients', err)
    })
  }, [query])

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
    </div>
  )
}

