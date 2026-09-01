import { request } from './client';

export const ingredientsApi = {
  fetchAll: () => request('/ingredients'),
  get: (id) => request(`/ingredients/${id}`),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
  create: (payload) =>
    request('/ingredients', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (id, payload) =>
    request(`/ingredients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  remove: (id, force = false) =>
    request(`/ingredients/${id}?force=${force}`, { method: 'DELETE' }),
  recipes: (id) => request(`/ingredients/${id}/recipes`),
  similar: (name, excludeId, threshold) =>
    request(
      `/ingredients/similar?name=${encodeURIComponent(name)}` +
        (excludeId ? `&exclude_id=${excludeId}` : '') +
        (threshold != null ? `&threshold=${threshold}` : '')
    ),
  duplicates: () => request('/ingredients/duplicates'),
  // Flips every ingredient whose conversions reach `dimension` to prefer it,
  // never touching counted ones. Writes a display preference, never a
  // quantity. Resolves `{ switched, skipped }`, both lists of names.
  switchPreferredDimension: (dimension) =>
    request('/ingredients/preferred-dimension', {
      method: 'POST',
      body: JSON.stringify({ preferred_dimension: dimension }),
    }),
  merge: (payload) =>
    request('/ingredients/merge', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
