import { request } from './client';

export const tagsApi = {
  fetchAll: () => request('/tags'),
};
