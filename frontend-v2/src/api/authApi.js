import { request } from './client';

export const authApi = {
  register: ({ email, password, display_name }) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: ({ email, password }) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => request('/auth/me'),
};
