import React from 'react'
import { XMarkIcon, CheckIcon } from '@heroicons/react/24/outline'
import { Input, Button } from './'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function SeasonalitySelect({ value = [], onChange }) {
  const [open, setOpen] = React.useState(false)

  const toggleMonth = (m) => {
    const next = value.includes(m)
      ? value.filter((v) => v !== m)
      : [...value, m]
    onChange(next)
  }

  return (
    <div className="relative">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setOpen((o) => !o)}
        className="whitespace-nowrap"
      >
        {value.length ? value.join(', ') : 'Seasonality'}
      </Button>
      {open && (
        <div
          className="absolute right-0 z-10 mt-1 w-36 rounded-xl border bg-white p-1 shadow"
          style={{ borderColor: 'var(--border)' }}
        >
          {MONTHS.map((m) => (
            <button
              type="button"
              key={m}
              onClick={() => toggleMonth(m)}
              className="flex w-full items-center justify-between rounded-lg px-2 py-1 text-sm hover:bg-[color:var(--c-a2)]/20"
            >
              <span>{m}</span>
              {value.includes(m) && <CheckIcon className="h-4 w-4" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function NewRecipeModal({ onClose, onSave }) {
  const [title, setTitle] = React.useState('')
  const [course, setCourse] = React.useState('')
  const [tags, setTags] = React.useState('')
  const [ingredients, setIngredients] = React.useState([
    { name: '', amount: '', unit: '', seasonality: [] },
  ])
  const [procedure, setProcedure] = React.useState('')
  const [bulkPrep, setBulkPrep] = React.useState(false)

  const updateIngredient = (idx, field, val) => {
    setIngredients((ings) =>
      ings.map((ing, i) => (i === idx ? { ...ing, [field]: val } : ing))
    )
  }

  const addIngredient = () =>
    setIngredients((ings) => [
      ...ings,
      { name: '', amount: '', unit: '', seasonality: [] },
    ])
  const removeIngredient = (idx) => {
    setIngredients((ings) => ings.filter((_, i) => i !== idx))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const recipe = {
      title,
      course,
      tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      ingredients: ingredients
        .filter((i) => i.name.trim())
        .map((ing, id) => ({
          id,
          name: ing.name,
          amount: parseFloat(ing.amount) || 0,
          unit: ing.unit,
          seasonality: ing.seasonality,
        })),
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
            <label className="text-sm">Tags</label>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="comma separated" />
          </div>
          <div className="space-y-2">
            <label className="text-sm">Ingredients</label>
            {ingredients.map((ing, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  value={ing.name}
                  onChange={(e) => updateIngredient(idx, 'name', e.target.value)}
                  className="flex-1"
                  placeholder="name"
                />
                <Input
                  type="number"
                  value={ing.amount}
                  onChange={(e) => updateIngredient(idx, 'amount', e.target.value)}
                  className="w-24"
                  placeholder="amt"
                />
                <select
                  value={ing.unit}
                  onChange={(e) => updateIngredient(idx, 'unit', e.target.value)}
                  className="rounded-xl border px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
                  style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
                >
                  <option value="">unit</option>
                  <option value="l">l</option>
                  <option value="g">g</option>
                  <option value="kg">kg</option>
                  <option value="pieces">pieces</option>
                </select>
                <SeasonalitySelect
                  value={ing.seasonality}
                  onChange={(val) => updateIngredient(idx, 'seasonality', val)}
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

