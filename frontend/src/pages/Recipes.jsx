import React, { useContext, useEffect, useState } from 'react'
import { AppContext } from '../App'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import IngredientRow from '../components/IngredientRow'
import TagSelector from '../components/TagSelector'
import { tagsApi, recipesApi, ingredientsApi } from '../api'

const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export default function Recipes() {
  const { recipes, setRecipes } = useContext(AppContext)
  const [availableTags, setAvailableTags] = useState([])
  const [showModal, setShowModal] = useState(false)

  const [title, setTitle] = useState('')
  const [course, setCourse] = useState('main')
  const [servings, setServings] = useState(1)
  const [procedure, setProcedure] = useState('')
  const [bulkPrep, setBulkPrep] = useState(false)
  const [selectedTags, setSelectedTags] = useState([])
  const [ingredients, setIngredients] = useState([])

  const refreshRecipes = () =>
    recipesApi
      .fetchAll()
      .then(setRecipes)
      .catch(() => setRecipes([]))

  useEffect(() => {
    tagsApi
      .fetchAll()
      .then(setAvailableTags)
      .catch(() => setAvailableTags([]))
    refreshRecipes()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fetchIngredientOptions = async (query) => {
    if (!query) return []
    try {
      return await ingredientsApi.search(query)
    } catch {
      return []
    }
  }

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

  const handleCreateTag = (name) => {
    tagsApi
      .create({ name })
      .then((tag) => setAvailableTags([...availableTags, tag]))
      .catch(() => setAvailableTags([...availableTags, { name }]))
  }

  const resetForm = () => {
    setTitle('')
    setCourse('main')
    setServings(1)
    setProcedure('')
    setBulkPrep(false)
    setSelectedTags([])
    setIngredients([])
  }

  const submit = async (e) => {
    e.preventDefault()
    const payload = {
      title,
      course,
      servings_default: Number(servings),
      procedure,
      bulk_prep: bulkPrep,
      tags: selectedTags,
      ingredients: ingredients.map((ing) => ({
        name: ing.name,
        quantity: ing.quantity === '' ? null : Number(ing.quantity),
        unit: ing.unit,
        season_months: ing.season.length ? ing.season : ALL_MONTHS,
      })),
    }
    try {
      await recipesApi.create(payload)
      await refreshRecipes()
      setShowModal(false)
      resetForm()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-medium">Recipes</h1>
        <Button variant="a1" onClick={() => setShowModal(true)}>
          + New recipe
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        {recipes.map((r) => (
          <Card key={r.id} size="sm" className="flex items-center justify-between">
            <div>
              <div className="font-medium">{r.title}</div>
              {r.course && (
                <div className="text-xs text-[color:var(--text-muted)]">[{r.course}]</div>
              )}
            </div>
          </Card>
        ))}
        {recipes.length === 0 && <p>No recipes yet.</p>}
      </div>
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card size="lg" className="w-full max-w-2xl">
            <form onSubmit={submit} className="flex flex-col gap-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  className="flex-1"
                />
                <Input
                  type="number"
                  min="1"
                  placeholder="Servings"
                  value={servings}
                  onChange={(e) => setServings(e.target.value)}
                  className="w-32"
                />
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={course}
                  onChange={(e) => setCourse(e.target.value)}
                  className="rounded-xl border px-3 py-2 text-sm flex-1"
                  style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
                >
                  <option value="main">main</option>
                  <option value="side">side</option>
                  <option value="dessert">dessert</option>
                </select>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="rounded border"
                    style={{ borderColor: 'var(--border)' }}
                    checked={bulkPrep}
                    onChange={(e) => setBulkPrep(e.target.checked)}
                  />
                  Bulk prep
                </label>
              </div>
              <textarea
                className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
                style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
                placeholder="Procedure"
                value={procedure}
                onChange={(e) => setProcedure(e.target.value)}
              />
              <TagSelector
                tags={availableTags}
                selected={selectedTags}
                onChange={setSelectedTags}
                onCreate={handleCreateTag}
              />
              <div>
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
                <Button type="button" size="sm" variant="ghost" onClick={addIngredient}>
                  Add Ingredient
                </Button>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowModal(false)
                    resetForm()
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="a1">
                  Save
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  )
}

