import { request } from './client';

export const ingredientsApi = {
  fetchAll: () => request('/ingredients'),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
  create: (data) =>
    request('/ingredients', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        unit: data.unit,
        season_months: data.season_months || data.season || [],
      }),
    }),
};
