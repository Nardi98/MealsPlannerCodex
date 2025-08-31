import { useEffect, useState } from 'react'
import { recipesApi } from '../api'
import { Card, Badge } from '../ui'

export default function RecipeList() {
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    recipesApi
      .fetchAll()
      .then(setRecipes)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p>Loading...</p>;
  }
  if (error) {
    return <p>Error: {error}</p>;
  }

  return (
    <Card>
      <ul className="space-y-1">
        {recipes.map((r) => (
          <li key={r.id}>
            {r.title}{' '}
            {r.score !== undefined && `(${r.score.toFixed(2)})`}{' '}
            {r.course && <Badge tone="a1">[{r.course}]</Badge>}{' '}
            {(r.tags || []).map((name) => (
              <Badge key={name} className="ml-1">
                {name}
              </Badge>
            ))}
          </li>
        ))}
      </ul>
    </Card>
  )
}
