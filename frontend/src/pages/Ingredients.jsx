import React, { useEffect, useRef, useState } from 'react'
import { ingredientsApi } from '../api'

export default function Ingredients() {
  const [ingredients, setIngredients] = useState([])
  const [editing, setEditing] = useState(null)
  const dialogRef = useRef(null)
  const [formName, setFormName] = useState('')
  const [formSeason, setFormSeason] = useState('')
  const [formUnit, setFormUnit] = useState('')

  useEffect(() => {
    ingredientsApi
      .fetchAll()
      .then(setIngredients)
      .catch(() => setIngredients([]))
  }, [])

  const openEdit = (ing) => {
    setEditing(ing)
    setFormName(ing.name)
    setFormSeason(ing.season_months.join(','))
    setFormUnit(ing.unit || '')
    dialogRef.current.showModal()
  }

  const closeEdit = () => {
    dialogRef.current.close()
    setEditing(null)
  }

  const saveEdit = async (e) => {
    e.preventDefault()
    const season = formSeason
      .split(',')
      .map((s) => Number(s.trim()))
      .filter((n) => !Number.isNaN(n))
    try {
      const updated = await ingredientsApi.update(editing.id, {
        name: formName,
        season_months: season,
        unit: formUnit,
      })
      setIngredients((ings) =>
        ings.map((i) => (i.id === updated.id ? updated : i))
      )
      closeEdit()
    } catch {
      // ignore errors
    }
  }

  return (
    <div>
      <h1>Ingredients</h1>
      {ingredients.length === 0 ? (
        <p>No ingredients found.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Season Months</th>
              <th>Unit</th>
              <th>Recipes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {ingredients.map((ing) => (
              <tr key={ing.id}>
                <td>{ing.name}</td>
                <td>{ing.season_months.join(', ')}</td>
                <td>{ing.unit}</td>
                <td>{ing.recipe_count}</td>
                <td>
                  <button type="button" onClick={() => openEdit(ing)}>
                    ✎
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <dialog ref={dialogRef}>
        {editing && (
          <form onSubmit={saveEdit}>
            <div>
              <label>
                Name:
                <input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                />
              </label>
            </div>
            <div>
              <label>
                Season months (comma separated):
                <input
                  value={formSeason}
                  onChange={(e) => setFormSeason(e.target.value)}
                />
              </label>
            </div>
            <div>
              <label>
                Unit:
                <select
                  value={formUnit}
                  onChange={(e) => setFormUnit(e.target.value)}
                >
                  <option value="">--</option>
                  <option value="g">g</option>
                  <option value="kg">kg</option>
                  <option value="l">l</option>
                  <option value="ml">ml</option>
                  <option value="piece">piece</option>
                </select>
              </label>
            </div>
            <button type="submit">Save</button>
            <button type="button" onClick={closeEdit}>
              Cancel
            </button>
          </form>
        )}
      </dialog>
    </div>
  )
}
