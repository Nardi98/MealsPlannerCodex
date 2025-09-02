import { request } from './client';

export const ingredientsApi = {
  fetchAll: () => request('/ingredients'),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
  update: (id, payload) =>
    request(`/ingredients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  remove: (id, force = false) =>
    request(`/ingredients/${id}?force=${force}`, { method: 'DELETE' }),
  recipes: (id) => request(`/ingredients/${id}/recipes`),
};
