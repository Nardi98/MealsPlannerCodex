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
};
