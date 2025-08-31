import { useEffect, useState } from 'react'
import { recipesApi } from '../api'
import RecipeCard from './RecipeCard'

export default function RecipeList() {
  const [recipes, setRecipes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    recipesApi
      .fetchAll()
      .then(setRecipes)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <p>Loading...</p>
  }
  if (error) {
    return <p>Error: {error}</p>
  }

  return (
    <div className="space-y-4">
      {recipes.map((r) => (
        <RecipeCard key={r.id} recipe={r} />
      ))}
    </div>
  )
}
