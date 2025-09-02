import { request } from './client';

export const tagsApi = {
  fetchAll: () => request('/tags'),
  create: (data) =>
    request('/tags', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
