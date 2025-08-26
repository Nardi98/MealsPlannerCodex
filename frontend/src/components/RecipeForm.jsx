import { useState } from 'react'
import IngredientRow from './IngredientRow'
import { recipesApi, ingredientsApi } from '../api'

export default function RecipeForm({ onCreated }) {
  const [title, setTitle] = useState('')
  const [servings, setServings] = useState('')
  const [course, setCourse] = useState('main course')
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
        season_months: ing.season,
      })),
    }
    try {
      const recipe = await recipesApi.create(payload)
      setTitle('')
      setServings('')
      setCourse('main course')
      setIngredients([])
      onCreated?.(recipe)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <p>Error: {error}</p>}
      <label>
        Title:
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Servings:
        <input value={servings} onChange={(e) => setServings(e.target.value)} />
      </label>
      <label>
        Course:
        <select value={course} onChange={(e) => setCourse(e.target.value)}>
          <option value="main course">main course</option>
          <option value="side dish">side dish</option>
          <option value="first course">first course</option>
        </select>
      </label>
      <div>
        <h3>Ingredients</h3>
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
        <button type="button" onClick={addIngredient}>
          Add Ingredient
        </button>
      </div>
      <button type="submit" disabled={loading}>
        {loading ? 'Saving...' : 'Save'}
      </button>
    </form>
  )
}
