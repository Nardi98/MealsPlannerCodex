import { request } from './client';

// The caller's plan settings (defaults + their stored overrides). The tag
// penalty weight lives here so it can be edited once from the profile rather
// than on every plan.
export const planSettingsApi = {
  get: () => request('/plan/settings'),
  update: (overrides) =>
    request('/plan/settings', {
      method: 'PUT',
      body: JSON.stringify(overrides),
    }),
};
