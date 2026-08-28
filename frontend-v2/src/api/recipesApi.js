import { request } from './client'
import { basisOf } from '../utils/servings';

const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

function normaliseRecipe(recipe) {
  return {
    id: recipe.id,
    title: recipe.title,
    course: recipe.course,
    score: recipe.score,
    image_url: recipe.image_url ?? null,
    // How many people the ingredient amounts below were written for.
    servings: basisOf(recipe.servings),
    hot: recipe.bulk_prep ?? false,
    tags: (recipe.tags || []).map((t) => (t.name ? t.name : t)),
    ingredients: (recipe.ingredients || []).map((ing) => ({
      id: ing.id,
      name: ing.name,
      amount: ing.quantity ?? '',
      unit: ing.unit ?? '',
    })),
    procedure: recipe.procedure || '',
    favorite_side_ids: recipe.favorite_side_ids || [],
    visibility: recipe.visibility ?? 'private',
    // AT-3 / AT-7: the attribution snapshot renders the permanent credit line,
    // and `copy_count` is the owner's "copied N times". Read-only — see
    // serialiseRecipe.
    copy_count: recipe.copy_count ?? 0,
    source_author_username: recipe.source_author_username ?? null,
    source_recipe_title: recipe.source_recipe_title ?? null,
    copied_at: recipe.copied_at ?? null,
  };
}

function serialiseRecipe(recipe) {
  return {
    title: recipe.title,
    course: recipe.course || 'main',
    // VIS-2: private unless the caller says otherwise. `public` is rejected by
    // the backend with 400.
    visibility: recipe.visibility || 'private',
    // AT-4: `copy_count` and the attribution snapshot are deliberately absent.
    // `RecipeIn` has no such fields, so sending them would be misleading noise
    // that reads as if the copier could edit their own credit line. They are
    // write-once, set by the copy path alone.
    procedure: recipe.procedure,
    bulk_prep: recipe.hot || false,
    image_url: recipe.image_url || null,
    servings: basisOf(recipe.servings),
    tags: recipe.tags || [],
    favorite_side_ids: recipe.favorite_side_ids || [],
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
  uploadImage: async (file) => {
    const body = new FormData();
    body.append('file', file);
    const res = await request('/recipes/upload-image', { method: 'POST', body });
    return res.image_url;
  },
};
