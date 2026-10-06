import { request } from './client';

export const mealPlansApi = {
  // The response passes straight through. A day is an array indexed by
  // meal_number, so a slot with no meal is a null hole rather than a missing
  // element, and one mishandled slot would blank the whole plan. Nothing needs
  // reshaping: `crud.meal_item` sends the title and a separate `leftover`
  // boolean, so no state is encoded in the title.
  fetchRange: (startDate, endDate) =>
    request(
      `/meal-plans?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    ),
  generate: async ({ start, end, ...params }) => {
    const data = await request('/meal-plans/generate', {
      method: 'POST',
      body: JSON.stringify({ start, end, ...params }),
    });
    return Object.fromEntries(
      Object.entries(data || {}).map(([day, meals]) => [
        day,
        meals.map((m) => ({
          id: m.id,
          title: m.title,
          leftover: Boolean(m.leftover),
          // The main's favorite side, picked by the planner. Empty when the
          // main has no favorites.
          side_ids: m.side_ids || [],
        })),
      ]),
    );
  },
  create: (payload, { force = false } = {}) =>
    request(`/meal-plans${force ? '?force=true' : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteRange: (startDate, endDate) =>
    request(
      `/meal-plans?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
      {
        method: 'DELETE',
      },
    ),
  accept: (planDate, mealNumber, accepted) =>
    request('/meal-plans/accept', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        accepted,
      }),
    }),
  swap: (a, b) =>
    request('/meal-plans/swap', {
      method: 'POST',
      body: JSON.stringify({ a, b }),
    }),
  setPeople: (planDate, mealNumber, people) =>
    request('/meal-plans/people', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        people,
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
