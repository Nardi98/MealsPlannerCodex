import React, { useContext, useState } from 'react'
import { AppContext } from '../App'
import IngredientRow from '../components/IngredientRow'

export default function Recipes() {
  const { recipes, setRecipes } = useContext(AppContext)
  const [title, setTitle] = useState('')
  const [servings, setServings] = useState(1)
  const [procedure, setProcedure] = useState('')
  const [bulkPrep, setBulkPrep] = useState(false)
  const [tagText, setTagText] = useState('')
  const [ingredients, setIngredients] = useState([])

  const addIngredient = () => {
    setIngredients([...ingredients, { name: '', quantity: '', unit: 'g', season: '' }])
  }

  const updateIngredient = (index, ing) => {
    const copy = [...ingredients]
    copy[index] = ing
    setIngredients(copy)
  }

  const removeIngredient = (index) => {
    const copy = ingredients.filter((_, i) => i !== index)
    setIngredients(copy)
  }

  const submit = (e) => {
    e.preventDefault()
    const tags = tagText.split(',').map((t) => t.trim()).filter(Boolean)
    const recipe = { title, servings, procedure, bulkPrep, tags, ingredients }
    setRecipes([...recipes, recipe])
    setTitle('')
    setServings(1)
    setProcedure('')
    setBulkPrep(false)
    setTagText('')
    setIngredients([])
  }

  const deleteRecipe = (idx) => {
    const copy = recipes.filter((_, i) => i !== idx)
    setRecipes(copy)
  }

  return (
    <div>
      <h1>Recipes</h1>
      <form onSubmit={submit}>
        <div>
          <label>Title </label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </div>
        <div>
          <label>Servings </label>
          <input type="number" min="1" value={servings} onChange={(e) => setServings(e.target.value)} />
        </div>
        <div>
          <label>Procedure </label>
          <textarea value={procedure} onChange={(e) => setProcedure(e.target.value)} />
        </div>
        <div>
          <label>
            <input type="checkbox" checked={bulkPrep} onChange={(e) => setBulkPrep(e.target.checked)} /> Bulk prep
          </label>
        </div>
        <div>
          <label>Tags (comma separated) </label>
          <input value={tagText} onChange={(e) => setTagText(e.target.value)} />
        </div>
        <div>
          <h3>Ingredients</h3>
          {ingredients.map((ing, idx) => (
            <IngredientRow
              key={idx}
              index={idx}
              ingredient={ing}
              onChange={updateIngredient}
              onRemove={removeIngredient}
            />
          ))}
          <button type="button" onClick={addIngredient}>Add Ingredient</button>
        </div>
        <button type="submit">Add Recipe</button>
      </form>
      <hr />
      {recipes.length === 0 && <p>No recipes yet.</p>}
      {recipes.map((r, idx) => (
        <div key={idx} style={{ borderBottom: '1px solid #ccc', padding: '0.5rem 0' }}>
          <h3>{r.title}</h3>
          {r.tags.map((t) => (
            <span key={t} className="recipe-tag">{t}</span>
          ))}
          <ul>
            {r.ingredients.map((ing, i) => (
              <li key={i}>{ing.quantity} {ing.unit} {ing.name}</li>
            ))}
          </ul>
          <button type="button" onClick={() => deleteRecipe(idx)}>Delete</button>
        </div>
      ))}
    </div>
  )
}
