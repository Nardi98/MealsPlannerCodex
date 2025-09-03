import React from 'react'
import { Card, Input, Button } from '../components'

export default function ShoppingListPage() {
  const [startDate, setStartDate] = React.useState('')
  const [endDate, setEndDate] = React.useState('')
  const [recipes, setRecipes] = React.useState([])
  const [ingredients, setIngredients] = React.useState([])

  React.useEffect(() => {
    const all = recipes
      .flatMap((r) => r.ingredients || [])
      .map((ing) => ({ id: ing.id, name: ing.name, done: false }))
    setIngredients(all)
  }, [recipes])

  return (
    <div className="space-y-4">
      <h1
        className="text-xl font-medium"
        style={{ color: 'var(--text-strong)' }}
      >
        Shopping List
      </h1>
      <div className="flex items-center gap-2">
        <Input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <Input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
        <Button variant="a1" onClick={() => setRecipes([])}>
          Load
        </Button>
      </div>
      <Card>
        {ingredients.map((ing) => (
          <div key={ing.id}>{ing.name}</div>
        ))}
      </Card>
    </div>
  )
}

