import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { Input, Button } from './'

export default function NewRecipeModal({ onClose, onSave }) {
  const [title, setTitle] = React.useState('')
  const [course, setCourse] = React.useState('')
  const [score, setScore] = React.useState('')
  const [tags, setTags] = React.useState('')
  const [ingredients, setIngredients] = React.useState([''])
  const [procedure, setProcedure] = React.useState('')
  const [bulkPrep, setBulkPrep] = React.useState(false)

  const updateIngredient = (idx, val) => {
    setIngredients((ings) => ings.map((ing, i) => (i === idx ? val : ing)))
  }

  const addIngredient = () => setIngredients((ings) => [...ings, ''])
  const removeIngredient = (idx) => {
    setIngredients((ings) => ings.filter((_, i) => i !== idx))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const recipe = {
      title,
      course,
      score: parseFloat(score) || 0,
      tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      ingredients: ingredients.filter((i) => i.trim()).map((name, id) => ({ id, name })),
      procedure,
      bulkPrep,
    }
    onSave?.(recipe)
    onClose?.()
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-lg" style={{ color: 'var(--text-strong)' }}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <h2 className="text-lg font-medium">New Recipe</h2>
          <div className="space-y-1">
            <label className="text-sm">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="space-y-1">
            <label className="text-sm">Course</label>
            <select
              value={course}
              onChange={(e) => setCourse(e.target.value)}
              required
              className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
              style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
            >
              <option value="">Select course</option>
              <option value="main">Main dish</option>
              <option value="side">Side dish</option>
              <option value="first-course">First course</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm">Score</label>
            <Input type="number" step="0.1" value={score} onChange={(e) => setScore(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-sm">Tags</label>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="comma separated" />
          </div>
          <div className="space-y-2">
            <label className="text-sm">Ingredients</label>
            {ingredients.map((ing, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  value={ing}
                  onChange={(e) => updateIngredient(idx, e.target.value)}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  Icon={XMarkIcon}
                  aria-label="Remove ingredient"
                  onClick={() => removeIngredient(idx)}
                />
              </div>
            ))}
            <Button type="button" variant="ghost" size="sm" onClick={addIngredient}>+ Add ingredient</Button>
          </div>
          <div className="space-y-1">
            <label className="text-sm">Procedure</label>
            <textarea value={procedure} onChange={(e) => setProcedure(e.target.value)} className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]" style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }} rows={3} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={bulkPrep} onChange={(e) => setBulkPrep(e.target.checked)} className="h-4 w-4 rounded accent-[color:var(--c-a1)] border" style={{ borderColor: 'var(--border)' }} />
            Bulk prep
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="a1">Save</Button>
          </div>
        </form>
      </div>
    </div>
  )
}

