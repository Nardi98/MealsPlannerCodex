import React from 'react'

export default function IngredientRow({ index, ingredient, onChange, onRemove }) {
  return (
    <div className="ingredient-row">
      <input
        type="text"
        placeholder={`Ingredient ${index + 1}`}
        value={ingredient.name}
        onChange={(e) => onChange(index, { ...ingredient, name: e.target.value })}
      />
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
