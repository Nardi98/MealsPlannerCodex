import { request } from './client';

export const ingredientsApi = {
  fetchAll: () => request('/ingredients'),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
};
