import React, { useContext, useMemo } from 'react'
import { AppContext } from '../App'

export default function GroceryList() {
  const { plan, recipes } = useContext(AppContext)

  const items = useMemo(() => {
    const map = new Map()
    Object.values(plan).forEach((meals) => {
      meals.forEach((title) => {
        if (title.endsWith(' (leftover)')) return
        const recipe = recipes.find((r) => r.title === title)
        if (!recipe) return
        ;(recipe.ingredients || []).forEach((ing) => {
          const key = `${ing.name}|${ing.unit || ''}`
          const existing = map.get(key) || { name: ing.name, unit: ing.unit || '', quantity: 0 }
          const qty = Number(ing.quantity) || 0
          existing.quantity += qty
          map.set(key, existing)
        })
      })
    })
    return Array.from(map.values())
  }, [plan, recipes])

  const handleExport = () => {
    const data = JSON.stringify(items, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'grocery_list.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (Object.keys(plan).length === 0) {
    return (
      <div>
        <h1>Grocery List</h1>
        <p>No plan loaded.</p>
      </div>
    )
  }

  return (
    <div>
      <h1>Grocery List</h1>
      <button type="button" onClick={handleExport}>Export</button>
      <ul>
        {items.map((item) => (
          <li key={`${item.name}-${item.unit}`}>
            {item.name}: {item.quantity}
            {item.unit ? ` ${item.unit}` : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}
