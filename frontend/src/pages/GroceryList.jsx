import React, { useContext, useMemo } from 'react'
import { AppContext } from '../App'

export default function GroceryList() {
  const { plan, recipes } = useContext(AppContext)

  const items = useMemo(() => {
    const acc = {}
    Object.values(plan).forEach((meals) => {
      meals.forEach(({ main, side }) => {
        ;[main, side].forEach((title) => {
          if (!title || title.endsWith(' (leftover)')) return
          const recipe = recipes.find((r) => r.title === title)
          if (!recipe) return
          ;(recipe.ingredients || []).forEach(({ name, quantity, unit }) => {
            const key = `${name}||${unit || ''}`
            if (!acc[key]) {
              acc[key] = {
                name,
                unit: unit || '',
                quantity: quantity ?? null,
              }
            } else if (acc[key].quantity != null && quantity != null) {
              acc[key].quantity += quantity
            } else {
              acc[key].quantity = null
            }
          })
        })
      })
    })
    return Object.values(acc).sort((a, b) => a.name.localeCompare(b.name))
  }, [plan, recipes])

  const handleExport = () => {
    const lines = items
      .map((ing) => {
        const qty = ing.quantity != null ? ing.quantity : ''
        const unit = ing.unit ? ` ${ing.unit}` : ''
        return `${ing.name}${qty !== '' ? `: ${qty}${unit}` : ''}`
      })
      .join('\n')
    const blob = new Blob([lines], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'grocery_list.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <h1>Grocery List</h1>
      <button type="button" onClick={handleExport} disabled={items.length === 0}>
        Export
      </button>
      {items.length === 0 ? (
        <p>No items</p>
      ) : (
        <ul>
          {items.map((ing) => (
            <li key={`${ing.name}-${ing.unit}`}>
              {ing.name}
              {ing.quantity != null ? `: ${ing.quantity}${ing.unit ? ` ${ing.unit}` : ''}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

