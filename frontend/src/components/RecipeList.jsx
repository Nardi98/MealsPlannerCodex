import { useEffect, useState } from 'react';
import { recipesApi } from '../api';

export default function RecipeList() {
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [order, setOrder] = useState('last_added');

  useEffect(() => {
    setLoading(true);
    recipesApi
      .fetchAll({ order })
      .then(setRecipes)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [order]);

  if (loading) {
    return <p>Loading...</p>;
  }
  if (error) {
    return <p>Error: {error}</p>;
  }

  return (
    <div>
      <label>
        Order:
        <select value={order} onChange={(e) => setOrder(e.target.value)}>
          <option value="last_added">Last added</option>
          <option value="title_asc">A-Z</option>
          <option value="title_desc">Z-A</option>
        </select>
      </label>
      <ul>
        {recipes.map((r) => (
          <li key={r.id}>
            {r.title}{' '}
            {r.score !== undefined && `(${r.score.toFixed(2)})`}
          </li>
        ))}
      </ul>
    </div>
  );
}
