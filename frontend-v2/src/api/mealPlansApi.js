import { request } from './client';

function parseMeal(meal) {
  let { recipe } = meal;
  let leftover = Boolean(meal.leftover);
  if (typeof recipe === 'string' && recipe.endsWith(' (leftover)')) {
    leftover = true;
    recipe = recipe.slice(0, -11);
  }
  return { ...meal, recipe, leftover };
}

export const mealPlansApi = {
  fetchRange: async (startDate, endDate) => {
    const data = await request(
      `/plan?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    );
    if (!data) return data;
    return Object.fromEntries(
      Object.entries(data).map(([day, meals]) => [
        day,
        meals.map((m) => parseMeal(m)),
      ]),
    );
  },
  generate: async (params) => {
    const data = await request('/meal-plans/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
    return Object.fromEntries(
      Object.entries(data || {}).map(([day, meals]) => [
        day,
        meals.map((m) => ({
          id: m.id,
          title: m.title,
          leftover: Boolean(m.leftover),
        })),
      ]),
    );
  },
  create: (payload, { force = false } = {}) =>
    request(`/plan${force ? '?force=true' : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload),
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
  addSide: (planDate, mealNumber, sideId, leftover = false) =>
    request('/meal-plans/side', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        side_id: sideId,
        leftover,
      }),
    }),
  replaceSide: (planDate, mealNumber, index, sideId, leftover = false) =>
    request('/meal-plans/side', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        index,
        side_id: sideId,
        leftover,
      }),
    }),
  removeSide: (planDate, mealNumber, index, leftover = false) =>
    request('/meal-plans/side', {
      method: 'DELETE',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        index,
        leftover,
      }),
    }),
};
