import { request } from './client';

export const feedbackApi = {
  acceptRecipe: (title) =>
    request('/feedback/accept', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  rejectRecipe: async (title) => {
    const res = await request('/feedback/reject', {
      method: 'POST',
      body: JSON.stringify({ title }),
    });
    return res.replacement;
  },
};

