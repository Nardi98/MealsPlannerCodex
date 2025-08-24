import React, { useContext, useState, useEffect } from 'react'
import { AppContext } from '../App'
import IngredientRow from '../components/IngredientRow'
import TagSelector from '../components/TagSelector'
import { tagsApi } from '../api'

export default function Recipes() {
  const { recipes, setRecipes } = useContext(AppContext)
  const [title, setTitle] = useState('')
  const [servings, setServings] = useState(1)
  const [procedure, setProcedure] = useState('')
  const [bulkPrep, setBulkPrep] = useState(false)
  const [availableTags, setAvailableTags] = useState([])
  const [selectedTags, setSelectedTags] = useState([])
  const [filterTags, setFilterTags] = useState([])
  const [ingredients, setIngredients] = useState([])
  const [editingIndex, setEditingIndex] = useState(null)

  useEffect(() => {
    tagsApi
      .fetchAll()
      .then(setAvailableTags)
      .catch(() => setAvailableTags([]))
  }, [])

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

  const handleCreateTag = (name) => {
    tagsApi
      .create({ name })
      .then((tag) => setAvailableTags([...availableTags, tag]))
      .catch(() => setAvailableTags([...availableTags, { name }]))
  }

  const submit = (e) => {
    e.preventDefault()
    const recipe = { title, servings, procedure, bulkPrep, tags: selectedTags, ingredients }
    if (editingIndex !== null) {
      const copy = [...recipes]
      copy[editingIndex] = recipe
      setRecipes(copy)
      setEditingIndex(null)
    } else {
      setRecipes([...recipes, recipe])
    }
    setTitle('')
    setServings(1)
    setProcedure('')
    setBulkPrep(false)
    setSelectedTags([])
    setIngredients([])
  }

  const deleteRecipe = (idx) => {
    const copy = recipes.filter((_, i) => i !== idx)
    setRecipes(copy)
  }

  const editRecipe = (idx) => {
    const r = recipes[idx]
    setTitle(r.title)
    setServings(r.servings)
    setProcedure(r.procedure)
    setBulkPrep(r.bulkPrep)
    setSelectedTags(
      (r.tags || []).map(
        (t) => availableTags.find((tag) => tag.id === t || tag.name === t)?.name || t
      )
    )
    setIngredients(r.ingredients)
    setEditingIndex(idx)
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
          <label>Tags </label>
          <TagSelector
            tags={availableTags}
            selected={selectedTags}
            onChange={setSelectedTags}
            onCreate={handleCreateTag}
          />
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
        <button type="submit">{editingIndex !== null ? 'Save Recipe' : 'Add Recipe'}</button>
      </form>
      <hr />
      <div>
        <label>Filter by tags </label>
        <TagSelector tags={availableTags} selected={filterTags} onChange={setFilterTags} />
      </div>
      {(() => {
        const filtered = filterTags.length
          ? recipes
              .map((r, idx) => ({ ...r, idx }))
              .filter((r) => filterTags.every((t) => r.tags.includes(t)))
          : recipes.map((r, idx) => ({ ...r, idx }))
        if (filtered.length === 0) {
          return <p>{recipes.length === 0 ? 'No recipes yet.' : 'No recipes match selected tags.'}</p>
        }
        return filtered.map(({ idx, ...r }) => (
          <div key={idx} style={{ borderBottom: '1px solid #ccc', padding: '0.5rem 0' }}>
            <h3>{r.title}</h3>
            {r.tags.map((t) => {
              const name = availableTags.find((tag) => tag.id === t || tag.name === t)?.name || t
              return (
                <span key={name} className="recipe-tag">{name}</span>
              )
            })}
            <ul>
              {r.ingredients.map((ing, i) => (
                <li key={i}>{ing.quantity} {ing.unit} {ing.name}</li>
              ))}
            </ul>
            <button type="button" onClick={() => editRecipe(idx)}>Edit</button>
            <button type="button" onClick={() => deleteRecipe(idx)}>Delete</button>
          </div>
        ))
      })()}
    </div>
  )
}
