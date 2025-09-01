import { request } from './client.js';

function createCrud(resource) {
  return {
    list: () => request(`/${resource}`),
    get: (id) => request(`/${resource}/${id}`),
    create: (data) =>
      request(`/${resource}`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id, data) =>
      request(`/${resource}/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    remove: (id) =>
      request(`/${resource}/${id}`, {
        method: 'DELETE',
      }),
  };
}

export const recipesApi = createCrud('recipes');
export const tagsApi = createCrud('tags');
export const feedbackApi = createCrud('feedback');
export const ingredientsApi = {
  ...createCrud('ingredients'),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
};

export const mealPlansApi = {
  list: () => request('/meal-plans'),
  create: (data) =>
    request('/meal-plans', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  accept: (data) =>
    request('/meal-plans/accept', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  addSide: (data) =>
    request('/meal-plans/side', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  removeSide: (data) =>
    request('/meal-plans/side', {
      method: 'DELETE',
      body: JSON.stringify(data),
    }),
};
