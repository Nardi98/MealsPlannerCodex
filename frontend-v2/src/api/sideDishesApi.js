import { request } from './client';

export const sideDishesApi = {
  // One side for the meal at `planDate` / `mealNumber`, scored against that
  // date. Sides already on the plate are left out by the server.
  generate: (planDate, mealNumber, { excludeIds = [] } = {}) =>
    request('/side-dishes/generate', {
      method: 'POST',
      body: JSON.stringify({ plan_date: planDate, meal_number: mealNumber, exclude_ids: excludeIds }),
    }),
};
