import { request } from './client';

// The meal plan's accept/reject signal, by recipe id and slot date. A reject
// suggests nothing: ask `mealPlansApi.replace` (a main) or
// `sideDishesApi.generate` (a side) for the replacement.
export const feedbackApi = {
  // A leftover accept marks nothing new: the batch was already counted once.
  acceptRecipe: (recipeId, planDate, { leftover = false } = {}) =>
    request('/feedback/accept', {
      method: 'POST',
      body: JSON.stringify({ recipe_id: recipeId, plan_date: planDate, leftover }),
    }),
  rejectRecipe: (recipeId, planDate) =>
    request('/feedback/reject', {
      method: 'POST',
      body: JSON.stringify({ recipe_id: recipeId, plan_date: planDate }),
    }),
};
