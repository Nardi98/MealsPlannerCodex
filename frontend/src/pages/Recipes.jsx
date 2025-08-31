import React, { useContext, useState, useEffect } from 'react'
import { AppContext } from '../App'
import IngredientRow from '../components/IngredientRow'
import TagSelector from '../components/TagSelector'
import { tagsApi, recipesApi, ingredientsApi } from '../api'
import { Card, Button, Input, Badge } from '../ui'
import { BookOpenIcon } from '@heroicons/react/24/outline'

const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export default function Recipes() {
  const { recipes, setRecipes } = useContext(AppContext)
  const [title, setTitle] = useState('')
  const [servings, setServings] = useState(1)
  const [procedure, setProcedure] = useState('')
  const [bulkPrep, setBulkPrep] = useState(false)
  const [course, setCourse] = useState('main')
  const [availableTags, setAvailableTags] = useState([])
  const [selectedTags, setSelectedTags] = useState([])
  const [filterTags, setFilterTags] = useState([])
  const [ingredients, setIngredients] = useState([])
  const [editingId, setEditingId] = useState(null)

  const fetchIngredientOptions = async (query) => {
    if (!query) return []
    try {
      return await ingredientsApi.search(query)
    } catch {
      return []
    }
  }

  const normalizeRecipe = (r) => ({
    id: r.id,
    title: r.title,
    score: r.score ?? 0,
    servings: r.servings ?? r.servings_default ?? 1,
    procedure: r.procedure || '',
    course: r.course ?? 'main',
    bulkPrep: r.bulkPrep ?? r.bulk_prep ?? false,
    tags: (r.tags || []).map((t) => t.name || t),
    ingredients: (r.ingredients || []).map((ing) => ({
      name: ing.name,
      quantity: ing.quantity ?? '',
      unit: ing.unit || 'g',
      season: ing.season_months || [],
    })),
  })

  const refreshRecipes = () =>
    recipesApi
      .fetchAll()
      .then((data) => setRecipes(data.map(normalizeRecipe)))
      .catch(() => setRecipes([]))

  useEffect(() => {
    tagsApi
      .fetchAll()
      .then(setAvailableTags)
      .catch(() => setAvailableTags([]))
    refreshRecipes()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const addIngredient = () => {
    setIngredients([...ingredients, { name: '', quantity: '', unit: 'g', season: [] }])
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
      if (editingId !== null) {
        await recipesApi.update(editingId, payload)
      } else {
        await recipesApi.create(payload)
      }
      await refreshRecipes()
      setEditingId(null)
      setTitle('')
      setServings(1)
      setProcedure('')
      setBulkPrep(false)
      setCourse('main')
      setSelectedTags([])
      setIngredients([])
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err)
    }
  }

  const deleteRecipe = async (id) => {
    try {
      await recipesApi.delete(id)
      await refreshRecipes()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err)
    }
  }

  const editRecipe = (r) => {
    setTitle(r.title)
    setServings(r.servings)
    setProcedure(r.procedure)
    setCourse(r.course)
    setBulkPrep(r.bulkPrep)
    setSelectedTags(r.tags)
    setIngredients(r.ingredients)
    setEditingId(r.id)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <BookOpenIcon className="h-6 w-6 text-[var(--c-a3)]" />
        <h1 className="text-2xl font-semibold">Recipes</h1>
      </div>
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} required className="mt-1 w-full" />
          </div>
          <div>
            <label className="block">Servings</label>
            <Input
              type="number"
              min="1"
              value={servings}
              onChange={(e) => setServings(e.target.value)}
              className="mt-1 w-full"
            />
          </div>
          <div>
            <label className="block">Course</label>
            <select
              value={course}
              onChange={(e) => setCourse(e.target.value)}
              className="mt-1 w-full rounded-xl border px-2 py-2 text-sm"
              style={{ borderColor: 'var(--border)' }}
            >
              <option value="main">main</option>
              <option value="side">side</option>
              <option value="first-course">first course</option>
            </select>
          </div>
          <div>
            <label className="block">Procedure</label>
            <textarea
              value={procedure}
              onChange={(e) => setProcedure(e.target.value)}
              className="mt-1 w-full rounded-xl border px-2 py-2 text-sm"
              style={{ borderColor: 'var(--border)' }}
            />
          </div>
          <div>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={bulkPrep}
                onChange={(e) => setBulkPrep(e.target.checked)}
                className="h-4 w-4"
                style={{ accentColor: 'var(--c-a1)' }}
              />
              Bulk prep
            </label>
          </div>
          <div>
            <label className="block mb-1">Tags</label>
            <TagSelector
              tags={availableTags}
              selected={selectedTags}
              onChange={setSelectedTags}
              onCreate={handleCreateTag}
            />
          </div>
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
            <Button type="button" variant="a1" onClick={addIngredient} className="mt-2">
              Add Ingredient
            </Button>
          </div>
          <Button type="submit" variant="primary">
            {editingId !== null ? 'Save Recipe' : 'Add Recipe'}
          </Button>
        </form>
      </Card>
      <Card>
        <div className="mb-4">
          <label className="block mb-1">Filter by tags</label>
          <TagSelector tags={availableTags} selected={filterTags} onChange={setFilterTags} />
        </div>
        {(() => {
          const filtered = filterTags.length
            ? recipes.filter((r) => filterTags.every((t) => (r.tags || []).includes(t)))
            : recipes
          if (filtered.length === 0) {
            return <p>{recipes.length === 0 ? 'No recipes yet.' : 'No recipes match selected tags.'}</p>
          }
          return filtered.map((r) => (
            <div
              key={r.id}
              className="mb-2 border-b pb-2 last:mb-0 last:border-b-0 last:pb-0"
              style={{ borderColor: 'var(--border)' }}
            >
              <h3>
                {r.title}{' '}
                {r.course && <Badge tone="a1">[{r.course}]</Badge>}{' '}
                <span style={{ fontSize: '0.9rem', fontWeight: 'normal' }}>
                  ({`Score: ${r.score.toFixed(2)}`})
                </span>
              </h3>
              {(r.tags || []).map((name) => (
                <Badge key={name} className="mr-1">
                  {name}
                </Badge>
              ))}
              <ul className="ml-4 list-disc">
                {(r.ingredients || []).map((ing, i) => (
                  <li key={i}>
                    {ing.quantity} {ing.unit} {ing.name}
                  </li>
                ))}
              </ul>
              <div className="mt-2 flex gap-2">
                <Button variant="a1" onClick={() => editRecipe(r)}>
                  Edit
                </Button>
                <Button variant="danger" onClick={() => deleteRecipe(r.id)}>
                  Delete
                </Button>
              </div>
            </div>
          ))
        })()}
      </Card>
    </div>
  )
}
