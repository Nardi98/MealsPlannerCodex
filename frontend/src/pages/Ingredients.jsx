import React, { useEffect, useState } from 'react'
import { ingredientsApi } from '../api'

export default function Ingredients() {
  const [ingredients, setIngredients] = useState([])
  const [search, setSearch] = useState('')
  const [order, setOrder] = useState('asc')
  const [editing, setEditing] = useState({})

  const load = () => {
    ingredientsApi
      .fetchAll({ search, order })
      .then(setIngredients)
      .catch(() => setIngredients([]))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, order])

  const handleChange = (id, field, value) => {
    setEditing({ ...editing, [id]: { ...editing[id], [field]: value } })
  }

  const save = async (id) => {
    try {
      await ingredientsApi.update(id, editing[id])
      setEditing((prev) => {
        const copy = { ...prev }
        delete copy[id]
        return copy
      })
      load()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err)
    }
  }

  return (
    <div>
      <h1>Ingredients</h1>
      <div>
        <input
          placeholder="Search ingredients"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="button" onClick={() => setOrder(order === 'asc' ? 'desc' : 'asc')}>
          Sort: {order === 'asc' ? 'A-Z' : 'Z-A'}
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Quantity</th>
            <th>Unit</th>
            <th>Season Months</th>
            <th>Recipe ID</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {ingredients.map((ing) => {
            const edit = editing[ing.id] || ing
            return (
              <tr key={ing.id}>
                <td>
                  <input
                    value={edit.name}
                    onChange={(e) => handleChange(ing.id, 'name', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={edit.quantity ?? ''}
                    onChange={(e) =>
                      handleChange(
                        ing.id,
                        'quantity',
                        e.target.value === '' ? null : Number(e.target.value)
                      )
                    }
                  />
                </td>
                <td>
                  <input
                    value={edit.unit ?? ''}
                    onChange={(e) => handleChange(ing.id, 'unit', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={(edit.season_months || []).join(',')}
                    onChange={(e) =>
                      handleChange(
                        ing.id,
                        'season_months',
                        e.target.value
                          .split(',')
                          .map((v) => Number(v.trim()))
                          .filter((v) => !Number.isNaN(v))
                      )
                    }
                  />
                </td>
                <td>{ing.recipe_id}</td>
                <td>
                  <button type="button" onClick={() => save(ing.id)}>
                    Save
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
