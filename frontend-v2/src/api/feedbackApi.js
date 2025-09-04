import { request } from './client';

export const feedbackApi = {
  acceptRecipe: (title, date) =>
    request('/feedback/accept', {
      method: 'POST',
      body: JSON.stringify({ title, consumed_date: date }),
    }),
  rejectRecipe: async (title, date) => {
    const res = await request('/feedback/reject', {
      method: 'POST',
      body: JSON.stringify({ title, consumed_date: date }),
    });
    return res.replacement;
  },
};

