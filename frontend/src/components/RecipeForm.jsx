import { useState } from 'react'
import IngredientRow from './IngredientRow'
import { recipesApi, ingredientsApi } from '../api'
import { Card, Button, Input } from '../ui'

const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export default function RecipeForm({ onCreated }) {
  const [title, setTitle] = useState('')
  const [servings, setServings] = useState('')
  const [course, setCourse] = useState('main')
  const [ingredients, setIngredients] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const addIngredient = () => {
    setIngredients([...ingredients, { name: '', quantity: '', unit: 'g', season: [] }])
  }

  const updateIngredient = (index, ing) => {
    const copy = [...ingredients]
    copy[index] = ing
    setIngredients(copy)
  }

  const removeIngredient = (index) => {
    setIngredients(ingredients.filter((_, i) => i !== index))
  }

  const fetchIngredientOptions = async (query) => {
    if (!query) return []
    try {
      return await ingredientsApi.search(query)
    } catch {
      return []
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const payload = {
      title,
      course,
      servings_default: Number(servings),
      ingredients: ingredients.map((ing) => ({
        name: ing.name,
        quantity: ing.quantity === '' ? null : Number(ing.quantity),
        unit: ing.unit,
        season_months: ing.season.length ? ing.season : ALL_MONTHS,
      })),
    }
    try {
      const recipe = await recipesApi.create(payload)
      setTitle('')
      setServings('')
      setCourse('main')
      setIngredients([])
      onCreated?.(recipe)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        {error && <p>Error: {error}</p>}
        <label className="block">
          Title:
          <Input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full" />
        </label>
        <label className="block">
          Servings:
          <Input value={servings} onChange={(e) => setServings(e.target.value)} className="mt-1 w-full" />
        </label>
        <label className="block">
          Course:
          <select
            value={course}
            onChange={(e) => setCourse(e.target.value)}
            className="mt-1 w-full rounded-xl border px-2 py-2 text-sm"
            style={{ borderColor: 'var(--border)' }}
          >
            <option value="main">main</option>
            <option value="side">side</option>
            <option value="dessert">dessert</option>
          </select>
        </label>
        <div>
          <h3 className="mb-2">Ingredients</h3>
          {ingredients.map((ing, idx) => (
            <IngredientRow
              key={idx}
              index={idx}
              ingredient={ing}
              onChange={updateIngredient}
              onRemove={removeIngredient}
              fetchOptions={fetchIngredientOptions}
            />
          ))}
          <Button variant="a1" type="button" onClick={addIngredient} className="mt-2">
            Add Ingredient
          </Button>
        </div>
        <Button type="submit" variant="primary" disabled={loading}>
          {loading ? 'Saving...' : 'Save'}
        </Button>
      </form>
    </Card>
  )
}
