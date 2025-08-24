import { useState } from 'react';
import { recipesApi } from '../api';

export default function RecipeForm({ onCreated }) {
  const [title, setTitle] = useState('');
  const [servings, setServings] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const payload = { title, servings_default: Number(servings) };
    try {
      const recipe = await recipesApi.create(payload);
      setTitle('');
      setServings('');
      onCreated?.(recipe);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit}>
      {error && <p>Error: {error}</p>}
      <label>
        Title:
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Servings:
        <input value={servings} onChange={(e) => setServings(e.target.value)} />
      </label>
      <button type="submit" disabled={loading}>
        {loading ? 'Saving...' : 'Save'}
      </button>
    </form>
  );
}
