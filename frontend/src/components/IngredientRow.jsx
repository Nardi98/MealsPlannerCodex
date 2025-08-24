import React, { useState } from 'react'

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

  return (
    <div className="ingredient-row">
      <input
        type="text"
        list={`ingredient-options-${index}`}
        placeholder={`Ingredient ${index + 1}`}
        value={ingredient.name}
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
        value={ingredient.quantity}
        onChange={(e) => onChange(index, { ...ingredient, quantity: e.target.value })}
      />
      <select
        value={ingredient.unit}
        onChange={(e) => onChange(index, { ...ingredient, unit: e.target.value })}
      >
        <option value="g">g</option>
        <option value="l">l</option>
        <option value="ml">ml</option>
        <option value="pieces">pieces</option>
      </select>
      <input
        type="text"
        placeholder="Season"
        value={ingredient.season}
        onChange={(e) => onChange(index, { ...ingredient, season: e.target.value })}
      />
      <button type="button" onClick={() => onRemove(index)}>✖</button>
    </div>
  )
}
