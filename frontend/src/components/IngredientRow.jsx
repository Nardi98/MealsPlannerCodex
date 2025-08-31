import React, { useState } from 'react'
import { Input, Button } from '../ui'

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

export default function IngredientRow({ index, ingredient, onChange, onRemove, fetchOptions }) {
  const [options, setOptions] = useState([])

  const handleNameChange = async (e) => {
    const value = e.target.value
    onChange(index, { ...ingredient, name: value })
    if (fetchOptions) {
      try {
        const opts = await fetchOptions(value)
        setOptions(opts)
      } catch {
        setOptions([])
      }
    }
  }

  const name = ingredient.name ?? ''
  const season = ingredient.season ?? []

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="text"
        list={`ingredient-options-${index}`}
        placeholder={`Ingredient ${index + 1}`}
        value={name}
        onChange={handleNameChange}
        className="flex-1"
      />
      <datalist id={`ingredient-options-${index}`}>
        {options.map((opt) => (
          <option key={opt.id || opt} value={opt.name || opt} />
        ))}
      </datalist>
      <Input
        type="number"
        placeholder="Qty"
        value={ingredient.quantity ?? ''}
        onChange={(e) => onChange(index, { ...ingredient, quantity: e.target.value })}
        className="w-24"
      />
      <select
        value={ingredient.unit}
        onChange={(e) => onChange(index, { ...ingredient, unit: e.target.value })}
        className="rounded-lg border px-2 py-2 text-sm"
        style={{ borderColor: 'var(--border)' }}
      >
        <option value="g">g</option>
        <option value="kg">kg</option>
        <option value="l">l</option>
        <option value="ml">ml</option>
        <option value="piece">piece</option>
      </select>
      <select
        multiple
        value={season.map((m) => String(m))}
        onChange={(e) =>
          onChange(index, {
            ...ingredient,
            season: Array.from(e.target.selectedOptions).map((o) => Number(o.value)),
          })
        }
        className="rounded-lg border px-2 py-2 text-sm"
        style={{ borderColor: 'var(--border)' }}
      >
        {MONTHS.map((m, i) => (
          <option key={i + 1} value={i + 1}>
            {m}
          </option>
        ))}
      </select>
      <Button variant="danger" onClick={() => onRemove(index)} className="px-2 py-1">
        ✖
      </Button>
    </div>
  )
}
