import { request } from './client';

function createCrud(resource) {
  return {
    fetchAll: () => request(`/${resource}`),
    fetch: (id) => request(`/${resource}/${id}`),
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
    delete: (id) =>
      request(`/${resource}/${id}`, {
        method: 'DELETE',
      }),
  };
}

function normaliseRecipe(recipe) {
  return {
    ...recipe,
    ingredients: (recipe.ingredients || []).map((ing) => ({
      id: ing.id,
      name: ing.name,
      quantity: ing.quantity ?? null,
      unit: ing.unit ?? null,
      season_months: ing.season_months ?? [],
    })),
  };
}

function serialiseRecipe(recipe) {
  return {
    ...recipe,
    ingredients: (recipe.ingredients || []).map((ing) => ({
      id: ing.id,
      name: ing.name,
      quantity: ing.quantity,
      unit: ing.unit,
      season_months: ing.season_months || ing.season || [],
    })),
  };
}

export const recipesApi = {
  fetchAll: async () => {
    const data = await request('/recipes')
    return data.map(normaliseRecipe)
  },
  fetch: async (id) => {
    const data = await request(`/recipes/${id}`)
    return normaliseRecipe(data)
  },
  create: async (data) => {
    const payload = serialiseRecipe(data)
    const res = await request('/recipes', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return normaliseRecipe(res)
  },
  update: async (id, data) => {
    const payload = serialiseRecipe(data)
    const res = await request(`/recipes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
    return normaliseRecipe(res)
  },
  delete: (id) => request(`/recipes/${id}`, { method: 'DELETE' }),
};
export const mealPlansApi = {
  ...createCrud('meal-plans'),
  create: async (data, { force = false } = {}) => {
    try {
      return await request(`/meal-plans${force ? '?force=true' : ''}`, {
        method: 'POST',
        body: JSON.stringify(data),
      })
    } catch (err) {
      if (err.data?.conflicts) {
        err.conflicts = err.data.conflicts
      }
      throw err
    }
  },
  generate: (data) =>
    request('/meal-plans/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  accept: (planDate, mealNumber, accepted) =>
    request('/meal-plans/accept', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        accepted,
      }),
    }),
};
export const tagsApi = createCrud('tags');
export const feedbackApi = createCrud('feedback');
export const ingredientsApi = {
  ...createCrud('ingredients'),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
};
