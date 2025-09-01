import { useState } from 'react'
import { Input } from './Input'
import { Button } from './Button'

export default function RecipeForm({ onSave, onCancel }) {
  const [title, setTitle] = useState('')
  const [course, setCourse] = useState('main')
  const [ingredients, setIngredients] = useState([''])
  const [tags, setTags] = useState('')
  const [procedure, setProcedure] = useState('')
  const [servings, setServings] = useState('')
  const [bulkPrep, setBulkPrep] = useState(false)

  const addIngredient = () => setIngredients([...ingredients, ''])
  const updateIngredient = (i, value) => {
    const copy = [...ingredients]
    copy[i] = value
    setIngredients(copy)
  }
  const removeIngredient = (i) => setIngredients(ingredients.filter((_, idx) => idx !== i))

  const submit = (e) => {
    e.preventDefault()
    const payload = {
      title,
      course,
      ingredients: ingredients.map((i) => i.trim()).filter(Boolean),
      tags: tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      procedure,
      servings: servings === '' ? null : Number(servings),
      bulkPrep,
    }
    onSave?.(payload)
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="title">
          Title
        </label>
        <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="course">
          Course
        </label>
        <select
          id="course"
          value={course}
          onChange={(e) => setCourse(e.target.value)}
          className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] w-full"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        >
          <option value="main">main</option>
          <option value="side">side</option>
          <option value="dessert">dessert</option>
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="servings">
            Servings
          </label>
          <Input
            id="servings"
            type="number"
            value={servings}
            onChange={(e) => setServings(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 pt-5">
          <input
            id="bulkPrep"
            type="checkbox"
            className="h-4 w-4 rounded border"
            style={{ borderColor: 'var(--border)' }}
            checked={bulkPrep}
            onChange={(e) => setBulkPrep(e.target.checked)}
          />
          <label htmlFor="bulkPrep" className="text-sm">
            Bulk prep
          </label>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Ingredients</label>
        {ingredients.map((ing, idx) => (
          <div key={idx} className="flex gap-2 mb-2">
            <Input
              className="flex-1"
              placeholder={`Ingredient ${idx + 1}`}
              value={ing}
              onChange={(e) => updateIngredient(idx, e.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => removeIngredient(idx)}
            >
              Remove
            </Button>
          </div>
        ))}
        <Button type="button" size="sm" variant="a2" onClick={addIngredient}>
          Add ingredient
        </Button>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="tags">
          Tags
        </label>
        <Input
          id="tags"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="comma separated"
        />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="procedure">
          Procedure
        </label>
        <textarea
          id="procedure"
          className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
          rows={4}
          value={procedure}
          onChange={(e) => setProcedure(e.target.value)}
        />
      </div>
      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="a1">
          Save
        </Button>
      </div>
    </form>
  )
}
