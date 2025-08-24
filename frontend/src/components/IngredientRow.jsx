import React, { useState } from 'react'

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
  'December'
]

export default function IngredientRow({ index, ingredient, onChange, onRemove, fetchOptions }) {
  const [options, setOptions] = useState([])

  const handleNameChange = async (e) => {
    const value = e.target.value
    const updated = {
      ...ingredient,
      ingredient: { ...(ingredient.ingredient || {}), name: value },
      name: undefined, // ensure legacy field isn't used
    }
    onChange(index, updated)
    if (fetchOptions) {
      try {
        const opts = await fetchOptions(value)
        setOptions(opts)
      } catch {
        setOptions([])
      }
    }
  }

  const name = ingredient.ingredient?.name ?? ingredient.name ?? ''
  const season = ingredient.ingredient?.season_months ?? ingredient.season ?? []

  return (
    <div className="ingredient-row">
      <input
        type="text"
        list={`ingredient-options-${index}`}
        placeholder={`Ingredient ${index + 1}`}
        value={name}
        onChange={handleNameChange}
      />
      <datalist id={`ingredient-options-${index}`}>
        {options.map((opt) => (
          <option key={opt.id || opt} value={opt.name || opt} />
        ))}
      </datalist>
      <input
        type="number"
        placeholder="Qty"
        value={ingredient.quantity ?? ''}
        onChange={(e) => onChange(index, { ...ingredient, quantity: e.target.value })}
      />
      <select
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
        value={season.map((m) => String(m))}
        onChange={(e) =>
          onChange(index, {
            ...ingredient,
            ingredient: {
              ...(ingredient.ingredient || {}),
              season_months: Array.from(e.target.selectedOptions).map((o) => Number(o.value)),
            },
            season: undefined,
          })
        }
      >
        {MONTHS.map((m, i) => (
          <option key={i + 1} value={i + 1}>
            {m}
          </option>
        ))}
      </select>
      <button type="button" onClick={() => onRemove(index)}>✖</button>
    </div>
  )
}
