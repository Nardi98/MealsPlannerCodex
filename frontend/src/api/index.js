import { request } from './client';

function createCrud(resource) {
  return {
    fetchAll: (params) => {
      const query = params ? `?${new URLSearchParams(params)}` : '';
      return request(`/${resource}${query}`);
    },
    fetch: (id) => request(`/${resource}/${id}`),
    create: (data) => request(`/${resource}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    update: (id, data) => request(`/${resource}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
    delete: (id) => request(`/${resource}/${id}`, {
      method: 'DELETE',
    }),
  };
}

export const recipesApi = createCrud('recipes');
export const mealPlansApi = {
  ...createCrud('meal-plans'),
  generate: (data) =>
    request('/meal-plans/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
export const tagsApi = createCrud('tags');
export const feedbackApi = createCrud('feedback');
export const ingredientsApi = {
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
};
