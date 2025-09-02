import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { Input, Button } from './'
import AddIngredientModal from './AddIngredientModal'

function IngredientDropdown({ value, options, onChange, onSelect, onAddNew }) {
  const [open, setOpen] = React.useState(false)
  const filtered = options.filter((o) =>
    o.name.toLowerCase().includes(value.toLowerCase())
  )
  return (
    <div className="relative flex-1">
      <Input
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 100)}
        placeholder="ingredient"
      />
      {open && (
        <div
          className="absolute z-10 mt-1 max-h-40 w-full overflow-auto rounded-md border bg-white"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        >
          {filtered.map((opt) => (
            <div
              key={opt.name}
              className="px-2 py-1 cursor-pointer hover:bg-gray-100"
              onMouseDown={() => {
                onSelect(opt)
                setOpen(false)
              }}
            >
              {opt.name}
            </div>
          ))}
          <div
            className="px-2 py-1 cursor-pointer hover:bg-gray-100"
            onMouseDown={() => {
              setOpen(false)
              onAddNew()
            }}
          >
            + Add new ingredient
          </div>
        </div>
      )}
    </div>
  )
}

export default function NewRecipeModal({ onClose, onSave }) {
  const [title, setTitle] = React.useState('')
  const [course, setCourse] = React.useState('')
  const [tags, setTags] = React.useState('')
  const [ingredients, setIngredients] = React.useState([{ name: '', amount: '', unit: '' }])
  const [procedure, setProcedure] = React.useState('')
  const [bulkPrep, setBulkPrep] = React.useState(false)
  const [ingredientOptions, setIngredientOptions] = React.useState([
    { name: 'Carrot', unit: 'g', season: [] },
    { name: 'Potato', unit: 'kg', season: [] },
    { name: 'Onion', unit: 'pieces', season: [] },
  ])
  const [addingIdx, setAddingIdx] = React.useState(null)

  const updateIngredient = (idx, field, val) => {
    setIngredients((ings) =>
      ings.map((ing, i) => (i === idx ? { ...ing, [field]: val } : ing))
    )
  }

  const addIngredient = () =>
    setIngredients((ings) => [...ings, { name: '', amount: '', unit: '' }])
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
        })),
      procedure,
      bulkPrep,
    }
    onSave?.(recipe)
    onClose?.()
  }

  const handleNewIngredient = (ing) => {
    setIngredientOptions((opts) => [...opts, ing])
    if (addingIdx != null) {
      updateIngredient(addingIdx, 'name', ing.name)
      updateIngredient(addingIdx, 'unit', ing.unit)
    }
    setAddingIdx(null)
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
                <IngredientDropdown
                  value={ing.name}
                  options={ingredientOptions}
                  onChange={(val) => {
                    updateIngredient(idx, 'name', val)
                    updateIngredient(idx, 'unit', '')
                  }}
                  onSelect={(opt) => {
                    updateIngredient(idx, 'name', opt.name)
                    updateIngredient(idx, 'unit', opt.unit)
                  }}
                  onAddNew={() => setAddingIdx(idx)}
                />
                <Input
                  type="number"
                  value={ing.amount}
                  onChange={(e) => updateIngredient(idx, 'amount', e.target.value)}
                  className="w-24"
                  placeholder="amt"
                />
                <span className="w-12 text-sm" style={{ color: 'var(--text-strong)' }}>
                  {ing.unit}
                </span>
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
            <textarea
              value={procedure}
              onChange={(e) => setProcedure(e.target.value)}
              className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
              style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
              rows={3}
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={bulkPrep}
              onChange={(e) => setBulkPrep(e.target.checked)}
              className="h-4 w-4 rounded accent-[color:var(--c-a1)] border"
              style={{ borderColor: 'var(--border)' }}
            />
            Bulk prep
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="a1">Save</Button>
          </div>
        </form>
      </div>
      {addingIdx != null && (
        <AddIngredientModal
          onClose={() => setAddingIdx(null)}
          onSave={handleNewIngredient}
        />
      )}
    </div>
  )
}

