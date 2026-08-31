import React from 'react'
import { Input, Button } from './'
import SeasonalitySelect from './SeasonalitySelect'
import CategorySelect from './CategorySelect'
import ConversionFields from './ConversionFields'
import { toConversions, fromConversions } from '../utils/conversionDraft'
import { ingredientsApi } from '../api/ingredientsApi'
import { ModalScrim } from './Modal'

export default function AddIngredientModal({ onClose, onSave, autoFocusField }) {
  const [name, setName] = React.useState('')
  const [conversions, setConversions] = React.useState(() => fromConversions())
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
    await onSave?.({ name, season_months: season, categories, ...toConversions(conversions) })
    onClose?.()
  }

  return (
    <ModalScrim>
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
          <ConversionFields
            value={conversions}
            onChange={setConversions}
            autoFocusField={autoFocusField}
          />
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
    </ModalScrim>
  )
}
