import { useEffect, useState } from 'react';
import { recipesApi } from '../api';

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
    <ul>
      {recipes.map((r) => (
        <li key={r.id}>
          {r.title} ({r.course}) {r.score !== undefined && `(${r.score.toFixed(2)})`}
        </li>
      ))}
    </ul>
  );
}
