import React from 'react'
import ExistingIngredientPicker from './ExistingIngredientPicker'

/**
 * Picks the ingredients the user has in the fridge. Each selection carries a
 * count — how many meals should be steered toward using it — adjusted with a
 * small stepper. State is lifted: `value` is `[{ ingredient_id, count }]` and
 * every change is reported through `onChange`.
 */
export default function FridgeSelector({ ingredients = [], value = [], onChange }) {
  const byId = React.useMemo(
    () => new Map(ingredients.map((i) => [i.id, i])),
    [ingredients]
  )

  const setCount = (ingredientId, count) => {
    if (count < 1) {
      onChange?.(value.filter((item) => item.ingredient_id !== ingredientId))
      return
    }
    onChange?.(
      value.map((item) =>
        item.ingredient_id === ingredientId ? { ...item, count } : item
      )
    )
  }

  const add = (ingredientId) => {
    if (value.some((item) => item.ingredient_id === ingredientId)) return
    onChange?.([...value, { ingredient_id: ingredientId, count: 1 }])
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: 'var(--text-subtle)' }}>
        Add ingredients you already have. The planner will favour recipes that use
        them first — pick an ingredient more than once to steer several meals.
      </p>
      <ExistingIngredientPicker options={ingredients} onChange={add} />
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {value.map((item) => {
            const ing = byId.get(item.ingredient_id)
            const name = ing ? ing.name : `#${item.ingredient_id}`
            return (
              <li
                key={item.ingredient_id}
                className="flex items-center gap-2 rounded-full border px-3 py-1 text-sm"
                style={{ borderColor: 'var(--border)' }}
              >
                <span style={{ color: 'var(--text-strong)' }}>{name}</span>
                <span className="flex items-center gap-1.5">
                  <button
                    type="button"
                    aria-label={`Decrease ${name}`}
                    onClick={() => setCount(item.ingredient_id, item.count - 1)}
                    className="grid h-5 w-5 place-items-center rounded-full border text-base leading-none"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-subtle)' }}
                  >
                    −
                  </button>
                  <span
                    className="min-w-[1ch] text-center font-medium"
                    style={{ color: 'var(--c-a2)' }}
                  >
                    {item.count}
                  </span>
                  <button
                    type="button"
                    aria-label={`Increase ${name}`}
                    onClick={() => setCount(item.ingredient_id, item.count + 1)}
                    className="grid h-5 w-5 place-items-center rounded-full border text-base leading-none"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-subtle)' }}
                  >
                    +
                  </button>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
