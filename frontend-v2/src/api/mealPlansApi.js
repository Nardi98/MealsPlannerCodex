import { request } from './client';

export const mealPlansApi = {
  fetchRange: (startDate, endDate) =>
    request(`/plan?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`),
  generate: (params) =>
    request('/meal-plans/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
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
  addSide: (planDate, mealNumber, sideId) =>
    request('/meal-plans/side', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        side_id: sideId,
      }),
    }),
  replaceSide: (planDate, mealNumber, index, sideId) =>
    request('/meal-plans/side', {
      method: 'POST',
      body: JSON.stringify({
        plan_date: planDate,
        meal_number: mealNumber,
        index,
        side_id: sideId,
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
};
