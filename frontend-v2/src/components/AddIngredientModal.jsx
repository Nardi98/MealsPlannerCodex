import React from 'react'
import { Input, Button } from './'
import SeasonalitySelect from './SeasonalitySelect'
import CategorySelect from './CategorySelect'
import { ingredientsApi } from '../api/ingredientsApi'

export default function AddIngredientModal({ onClose, onSave }) {
  const [name, setName] = React.useState('')
  const [unit, setUnit] = React.useState('')
  const [season, setSeason] = React.useState([])
  const [categories, setCategories] = React.useState([])
  const [similar, setSimilar] = React.useState([])

  const checkSimilar = React.useCallback(async (value) => {
    const trimmed = value.trim()
    if (!trimmed) {
      setSimilar([])
      return
    }
    try {
      const matches = await ingredientsApi.similar(trimmed)
      setSimilar(matches || [])
    } catch (err) {
      console.error('Failed to check similar ingredients', err)
    }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    await onSave?.({ name, unit, season, categories })
    onClose?.()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md" style={{ color: 'var(--text-strong)' }}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <h3 className="text-lg font-medium">New Ingredient</h3>
          <div className="space-y-1">
            <label className="text-sm">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={(e) => checkSimilar(e.target.value)}
              required
            />
            {similar.length > 0 && (
              <div className="text-xs" style={{ color: 'var(--c-a2)' }}>
                Similar exists: {similar.map((s) => s.name).join(', ')} — did you
                mean one of these?
              </div>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-sm">Unit</label>
            <select
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              required
              className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
              style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
            >
              <option value="">Select unit</option>
              <option value="g">g</option>
              <option value="kg">kg</option>
              <option value="l">l</option>
              <option value="ml">ml</option>
              <option value="piece">piece</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm">Seasonality</label>
            <SeasonalitySelect value={season} onChange={setSeason} />
          </div>
          <div className="space-y-1">
            <label className="text-sm">Categories</label>
            <CategorySelect value={categories} onChange={setCategories} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="a1">Save</Button>
          </div>
        </form>
      </div>
    </div>
  )
}
