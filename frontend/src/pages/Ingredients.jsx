import React, { useEffect, useState } from 'react'
import { ingredientsApi } from '../api'

export default function Ingredients() {
  const [ingredients, setIngredients] = useState([])

  useEffect(() => {
    ingredientsApi
      .fetchAll()
      .then(setIngredients)
      .catch(() => setIngredients([]))
  }, [])

  return (
    <div>
      <h1>Ingredients</h1>
      {ingredients.length === 0 ? (
        <p>No ingredients found.</p>
      ) : (
        <ul>
          {ingredients.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
