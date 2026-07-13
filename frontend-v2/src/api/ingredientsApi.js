import { request } from './client';

export const ingredientsApi = {
  fetchAll: () => request('/ingredients'),
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
  similar: (name, excludeId) =>
    request(
      `/ingredients/similar?name=${encodeURIComponent(name)}` +
        (excludeId ? `&exclude_id=${excludeId}` : '')
    ),
  duplicates: () => request('/ingredients/duplicates'),
  merge: (payload) =>
    request('/ingredients/merge', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
