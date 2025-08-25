import React, { useContext, useEffect, useState } from 'react'
import { AppContext } from '../App'
import { recipesApi } from '../api'

export default function GroceryList() {
  const { plan, recipes, setRecipes } = useContext(AppContext)
  const [items, setItems] = useState([])

  useEffect(() => {
    async function buildList() {
      let list = recipes
      if (list.length === 0) {
        try {
          list = await recipesApi.fetchAll()
          setRecipes(list)
        } catch {
          list = []
        }
      }
      const titleMap = {}
      list.forEach((r) => {
        titleMap[r.title] = r
      })
      const agg = {}
      Object.values(plan).forEach((meals) => {
        meals.forEach((meal) => {
          if (meal.endsWith(' (leftover)')) return
          const recipe = titleMap[meal]
          if (recipe) {
            recipe.ingredients.forEach((ing) => {
              const key = `${ing.name}|${ing.unit || ''}`
              const qty = Number(ing.quantity) || 0
              if (!agg[key]) {
                agg[key] = { name: ing.name, unit: ing.unit || '', quantity: qty }
              } else {
                agg[key].quantity += qty
              }
            })
          }
        })
      })
      setItems(Object.values(agg))
    }
    buildList()
  }, [plan, recipes, setRecipes])

  const handleExport = () => {
    const lines = items.map((i) =>
      `${i.name}${i.quantity ? ` ${i.quantity}` : ''}${i.unit ? ` ${i.unit}` : ''}`
    )
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'grocery-list.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (items.length === 0) {
    return (
      <div>
        <h1>Grocery List</h1>
        <p>No items.</p>
      </div>
    )
  }

  return (
    <div>
      <h1>Grocery List</h1>
      <button type="button" onClick={handleExport}>
        Export
      </button>
      <ul>
        {items.map((i) => (
          <li key={`${i.name}-${i.unit}`}>
            {i.name}
            {i.quantity ? ` ${i.quantity}` : ''}
            {i.unit ? ` ${i.unit}` : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}

