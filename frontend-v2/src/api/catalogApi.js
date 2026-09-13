import { request } from './client';

// The system recipe catalog ("Discover", spec §10.1).
//
// Rows pass through unnormalised, like `sharedWithMeApi`: the backend builds
// them from an explicit field allowlist (API-7/8), and reshaping them here
// would create a second, drifting copy of that list. They are also kept out of
// `recipesApi` on purpose -- a catalog recipe is not in the user's book until
// it has been adopted.

// `course` and `tags` are repeatable keys (`?course=main&course=side`), which
// is why this appends rather than building the string from an object. Empty
// values are dropped so an unset filter is absent, not sent blank.
function listQuery({ courses = [], tags = [], q, sort } = {}) {
  const params = new URLSearchParams();
  courses.forEach((course) => params.append('course', course));
  tags.forEach((tag) => params.append('tags', tag));
  if (q && q.trim()) params.append('q', q.trim());
  if (sort) params.append('sort', sort);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export const catalogApi = {
  // Published catalog recipes, filtered, searched and sorted server-side.
  list: (filters) => request(`/catalog/recipes${listQuery(filters)}`),

  // One published recipe, with its procedure (UI-7). 404 unless published.
  get: (recipeId) => request(`/catalog/recipes/${encodeURIComponent(recipeId)}`),

  // Copy recipes into the caller's book in one transaction
  // → { created_ids, skipped_ids }.
  adopt: (recipeIds) =>
    request('/catalog/adopt', {
      method: 'POST',
      body: JSON.stringify({ recipe_ids: recipeIds }),
    }),
};

export default catalogApi;
