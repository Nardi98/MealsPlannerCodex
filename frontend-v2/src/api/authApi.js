import { request } from './client';

// Mirrors the server-side password policy: 8–72 bytes, with at least one
// uppercase, one lowercase, and one digit. Returns an error message string, or
// null when the password is acceptable.
export function validatePassword(password) {
  const value = password || '';
  const bytes =
    typeof TextEncoder !== 'undefined'
      ? new TextEncoder().encode(value).length
      : value.length;
  if (bytes < 8) return 'Password must be at least 8 characters.';
  if (bytes > 72) return 'Password must be at most 72 bytes.';
  if (!/[A-Z]/.test(value)) return 'Password must include an uppercase letter.';
  if (!/[a-z]/.test(value)) return 'Password must include a lowercase letter.';
  if (!/[0-9]/.test(value)) return 'Password must include a digit.';
  return null;
}

export const authApi = {
  // No auto-login: the account starts unverified and the server emails a
  // verification link. Returns the created user.
  register: ({ email, password, display_name }) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),
  // On success the server sets the HttpOnly refresh cookie and returns the
  // access token. 403 when the email is not yet verified.
  login: ({ email, password }) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  google: ({ credential }) =>
    request('/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    }),
  // Exchanges the refresh cookie for a fresh access token.
  refresh: () => request('/auth/refresh', { method: 'POST' }),
  // Clears the refresh cookie server-side (204).
  logout: () => request('/auth/logout', { method: 'POST' }),
  verifyEmail: (token) =>
    request('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  // Always resolves with a neutral 200 regardless of whether the email exists.
  forgotPassword: (email) =>
    request('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token, newPassword) =>
    request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  me: () => request('/auth/me'),
  setDefaultPeople: ({ people, startDate, endDate }) =>
    request('/auth/me/default-people', {
      method: 'PUT',
      body: JSON.stringify({
        people,
        start_date: startDate,
        end_date: endDate,
      }),
    }),
};
