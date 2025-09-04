import { request } from './client';

export const dataApi = {
  exportDatabase: () => request('/data/export'),
  importDatabase: (payload, mode) =>
    request(`/data/import?mode=${mode}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  clearDatabase: () => request('/data', { method: 'DELETE' }),
};

