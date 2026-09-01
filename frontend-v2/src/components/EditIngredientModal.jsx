import React from 'react'
import { Input, Button } from './'
import SeasonalitySelect from './SeasonalitySelect'
import CategorySelect from './CategorySelect'
import ConversionFields from './ConversionFields'
import { toConversions, fromConversions } from '../utils/conversionDraft'
import { ModalScrim } from './Modal'

export default function EditIngredientModal({
  ingredient,
  onClose,
  onSave,
  autoFocusField,
}) {
  const [name, setName] = React.useState(ingredient?.name || '')
  const [conversions, setConversions] = React.useState(() =>
    fromConversions(ingredient),
  )
  const [season, setSeason] = React.useState(ingredient?.season_months || [])
  const [categories, setCategories] = React.useState(ingredient?.categories || [])

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave?.({ name, season_months: season, categories, ...toConversions(conversions) })
  }

  return (
    <ModalScrim>
      <div className="bg-white rounded-2xl p-6 w-full max-w-md" style={{ color: 'var(--text-strong)' }}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <h3 className="text-lg font-medium">Edit Ingredient</h3>
          <div className="space-y-1">
            <label className="text-sm">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
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
