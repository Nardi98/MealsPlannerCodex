import React from 'react'
import { Input, Button } from './'
import SeasonalitySelect from './SeasonalitySelect'

export default function AddIngredientModal({ onClose, onSave }) {
  const [name, setName] = React.useState('')
  const [unit, setUnit] = React.useState('')
  const [season, setSeason] = React.useState([])

  const handleSubmit = async (e) => {
    e.preventDefault()
    await onSave?.({ name, unit, season })
    onClose?.()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md" style={{ color: 'var(--text-strong)' }}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <h3 className="text-lg font-medium">New Ingredient</h3>
          <div className="space-y-1">
            <label className="text-sm">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
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
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="a1">Save</Button>
          </div>
        </form>
      </div>
    </div>
  )
}

