import { request } from './client';

const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

function normaliseRecipe(recipe) {
  return {
    id: recipe.id,
    title: recipe.title,
    course: recipe.course,
    score: recipe.score,
    hot: recipe.bulk_prep ?? false,
    tags: (recipe.tags || []).map((t) => (t.name ? t.name : t)),
    ingredients: (recipe.ingredients || []).map((ing) => ({
      id: ing.id,
      name: ing.name,
      amount: ing.quantity ?? '',
      unit: ing.unit ?? '',
    })),
    procedure: recipe.procedure || '',
  };
}

function serialiseRecipe(recipe) {
  return {
    title: recipe.title,
    course: recipe.course || 'main',
    servings_default: 1,
    procedure: recipe.procedure,
    bulk_prep: recipe.hot || false,
    tags: recipe.tags || [],
    ingredients: (recipe.ingredients || []).map((ing) => ({
      id: ing.id,
      name: ing.name,
      quantity:
        ing.amount !== undefined && ing.amount !== ''
          ? parseFloat(ing.amount)
          : null,
      unit: ing.unit || null,
      season_months: ing.season_months || ALL_MONTHS,
    })),
  };
}

export const recipesApi = {
  fetchAll: async () => {
    const data = await request('/recipes');
    return data.map(normaliseRecipe);
  },
  fetch: async (id) => {
    const data = await request(`/recipes/${id}`);
    return normaliseRecipe(data);
  },
  create: async (data) => {
    const payload = serialiseRecipe(data);
    const res = await request('/recipes', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return normaliseRecipe(res);
  },
  update: async (id, data) => {
    const payload = serialiseRecipe(data);
    const res = await request(`/recipes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return normaliseRecipe(res);
  },
  delete: (id) => request(`/recipes/${id}`, { method: 'DELETE' }),
};
