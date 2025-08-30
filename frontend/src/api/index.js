import { request } from './client';

const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

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
    ingredients: (recipe.ingredients || []).map((ing) => {
      const months = ing.season_months ?? ing.season;
      return {
        id: ing.id,
        name: ing.name,
        quantity: ing.quantity,
        unit: ing.unit,
        season_months: months && months.length ? months : ALL_MONTHS,
      };
    }),
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
    const serialisePlan = (plan) => {
      const out = {}
      Object.entries(plan).forEach(([day, meals]) => {
        out[day] = meals.map((m) => {
          if (typeof m === 'number' || typeof m === 'string') return m
          if ('main_id' in m || 'side_ids' in m) return m
          const res = { main_id: m.main }
          if (m.sides && m.sides.length) res.side_ids = m.sides
          return res
        })
      })
      return out
    }
    const payload = data.plan ? { ...data, plan: serialisePlan(data.plan) } : data
    try {
      return await request(`/meal-plans${force ? '?force=true' : ''}`, {
        method: 'POST',
        body: JSON.stringify(payload),
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
  addSide: (planDate, mealNumber, sideId, index) =>
    request('/meal-plans/side', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        side_id: sideId,
        index,
      }),
    }),
  removeSide: (planDate, mealNumber, index) =>
    request('/meal-plans/side', {
      method: 'DELETE',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        index,
      }),
    }),
  generateSide: (payload) =>
    request('/side-dishes/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
export const tagsApi = createCrud('tags');
export const feedbackApi = createCrud('feedback');
export const ingredientsApi = {
  ...createCrud('ingredients'),
  search: (q) => request(`/ingredients?search=${encodeURIComponent(q)}`),
};
