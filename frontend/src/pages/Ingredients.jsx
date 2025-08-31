import React, { useEffect, useRef, useState } from 'react'
import { ingredientsApi } from '../api'
import { Button, Card, Input } from '../ui'
import { PencilSquareIcon } from '@heroicons/react/24/outline'

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
      <h1 style={{ color: 'var(--text-strong)' }}>Ingredients</h1>
      {ingredients.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No ingredients found.</p>
      ) : (
        <Card className="mt-4">
          <table
            className="table-auto w-full border text-sm"
            style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
          >
            <thead>
              <tr>
                {['Name', 'Season Months', 'Unit', 'Recipes', ''].map((h) => (
                  <th
                    key={h}
                    className="border p-2 text-left"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ingredients.map((ing) => (
                <tr key={ing.id} className="odd:bg-[var(--c-white)]">
                  <td className="border p-2" style={{ borderColor: 'var(--border)' }}>
                    {ing.name}
                  </td>
                  <td className="border p-2" style={{ borderColor: 'var(--border)' }}>
                    {ing.season_months.join(', ')}
                  </td>
                  <td className="border p-2" style={{ borderColor: 'var(--border)' }}>
                    {ing.unit}
                  </td>
                  <td className="border p-2" style={{ borderColor: 'var(--border)' }}>
                    {ing.recipe_count}
                  </td>
                  <td className="border p-2 text-right" style={{ borderColor: 'var(--border)' }}>
                    <Button
                      variant="a1"
                      type="button"
                      Icon={PencilSquareIcon}
                      onClick={() => openEdit(ing)}
                      className="px-2 py-1"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <dialog ref={dialogRef} className="rounded-lg p-4">
        {editing && (
          <form onSubmit={saveEdit} className="space-y-3">
            <div className="flex flex-col">
              <label className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Name:
              </label>
              <Input value={formName} onChange={(e) => setFormName(e.target.value)} />
            </div>
            <div className="flex flex-col">
              <label className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Season months (comma separated):
              </label>
              <Input
                value={formSeason}
                onChange={(e) => setFormSeason(e.target.value)}
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Unit:
              </label>
              <select
                value={formUnit}
                onChange={(e) => setFormUnit(e.target.value)}
                className="rounded-lg border px-4 py-2 text-sm"
                style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
              >
                <option value="">--</option>
                <option value="g">g</option>
                <option value="kg">kg</option>
                <option value="l">l</option>
                <option value="ml">ml</option>
                <option value="piece">piece</option>
              </select>
            </div>
            <div className="flex gap-2 justify-end">
              <Button type="submit" variant="primary">
                Save
              </Button>
              <Button type="button" variant="ghost" onClick={closeEdit}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </dialog>
    </div>
  )
}
