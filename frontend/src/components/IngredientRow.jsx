import React, { useState } from 'react'
import { Input } from './Input'
import { Button } from './Button'

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
    <div className="flex items-center gap-2 mb-2">
      <Input
        type="text"
        size="sm"
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
        size="sm"
        placeholder="Qty"
        value={ingredient.quantity ?? ''}
        onChange={(e) => onChange(index, { ...ingredient, quantity: e.target.value })}
        className="w-20"
      />
      <select
        className="rounded-xl border px-2 py-1 text-sm"
        style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        value={ingredient.unit}
        onChange={(e) => onChange(index, { ...ingredient, unit: e.target.value })}
      >
        <option value="g">g</option>
        <option value="kg">kg</option>
        <option value="l">l</option>
        <option value="ml">ml</option>
        <option value="piece">piece</option>
      </select>
      <select
        multiple
        className="rounded-xl border px-2 py-1 text-sm"
        style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        value={season.map((m) => String(m))}
        onChange={(e) =>
          onChange(index, {
            ...ingredient,
            season: Array.from(e.target.selectedOptions).map((o) => Number(o.value)),
          })
        }
      >
        {MONTHS.map((m, i) => (
          <option key={i + 1} value={i + 1}>
            {m}
          </option>
        ))}
      </select>
      <Button
        type="button"
        variant="danger"
        size="sm"
        onClick={() => onRemove(index)}
      >
        ✖
      </Button>
    </div>
  )
}
