import { request } from './client';

export const sideDishesApi = {
  generate: (params) =>
    request('/side-dishes/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
};

