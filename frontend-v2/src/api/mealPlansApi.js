import { request } from './client';

export const mealPlansApi = {
  fetchRange: (startDate, endDate) =>
    request(`/plan?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`),
  generate: (params) =>
    request('/plan/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  create: (payload, { force = false } = {}) =>
    request(`/plan${force ? '?force=true' : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
