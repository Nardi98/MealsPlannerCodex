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
const stripLeftover = (t) => (typeof t === 'string' ? t.replace(/ \(leftover\)$/, '') : t)

async function serialisePlan(plan) {
  let needsLookup = false
  Object.values(plan).forEach((meals) => {
    meals.forEach((m) => {
      if (typeof m === 'object') {
        if (typeof m.main === 'string') needsLookup = true
        if ((m.sides || []).some((s) => typeof s === 'string')) needsLookup = true
      }
    })
  })
  let titleToId = new Map()
  if (needsLookup) {
    const recipes = await request('/recipes')
    if (Array.isArray(recipes)) {
      titleToId = new Map(recipes.map((r) => [r.title, r.id]))
    }
  }
  const out = {}
  Object.entries(plan).forEach(([day, meals]) => {
    out[day] = meals.map((m) => {
      if (typeof m === 'number' || typeof m === 'string') return m
      if ('main_id' in m || 'side_ids' in m) return m
      const mainId =
        typeof m.main === 'number' ? m.main : titleToId.get(stripLeftover(m.main))
      const sideIds = (m.sides || [])
        .map((s) => (typeof s === 'number' ? s : titleToId.get(stripLeftover(s))))
        .filter((id) => id !== undefined)
      const res = { main_id: mainId }
      if (sideIds.length) res.side_ids = sideIds
      return res
    })
  })
  return out
}

async function deserialisePlan(plan) {
  const recipes = await request('/recipes')
  const idToTitle = Array.isArray(recipes)
    ? new Map(recipes.map((r) => [r.id, r.title]))
    : new Map()
  const out = {}
  Object.entries(plan).forEach(([day, meals]) => {
    out[day] = meals.map((m) => {
      const mainId = m.main_id ?? m.main
      const sides = m.side_ids || []
      return {
        main: idToTitle.get(mainId) || m.recipe || m.title || mainId,
        sides: sides.map((id) => idToTitle.get(id) || id),
      }
    })
  })
  return out
}

export const mealPlansApi = {
  fetchAll: async () => {
    const data = await request('/meal-plans')
    return deserialisePlan(data)
  },
  fetch: async (id) => {
    const data = await request(`/meal-plans/${id}`)
    return deserialisePlan(data)
  },
  create: async (data, { force = false } = {}) => {
    const payload = data.plan ? { ...data, plan: await serialisePlan(data.plan) } : data
    try {
      const res = await request(`/meal-plans${force ? '?force=true' : ''}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      return deserialisePlan(res)
    } catch (err) {
      if (err.data?.conflicts) {
        err.conflicts = err.data.conflicts
      }
      throw err
    }
  },
  update: async (id, data) => {
    const payload = data.plan ? { ...data, plan: await serialisePlan(data.plan) } : data
    const res = await request(`/meal-plans/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
    return deserialisePlan(res)
  },
  delete: (id) => request(`/meal-plans/${id}`, { method: 'DELETE' }),
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
