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

// The server rejects `u` longer than this with a 422 (`username_routes.py`'s
// `_MAX_QUERY_LENGTH`). Answering locally keeps a paste-bomb from consuming one
// of the caller's 30-per-minute checks (UN-7).
export const USERNAME_QUERY_MAX_LENGTH = 64;

export const authApi = {
  // No auto-login: the account starts unverified and the server emails a
  // verification link. Returns the created user.
  // `username` is the account's public handle (UN-1/UN-5). It is omitted rather
  // than sent as null when the caller has none, so the server falls back to
  // deriving one from the email instead of failing validation.
  register: ({ email, password, display_name, username }) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        display_name,
        ...(username ? { username } : {}),
      }),
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
  // UN-7. Unauthenticated GET, rate-limited to 30/minute server-side, so callers
  // must debounce. Resolves `{ available, reason }`; `reason` is "taken",
  // "reserved", or a validation message, and null when the handle is free. The
  // candidate is never logged — it is unvalidated user input.
  checkUsername: (handle) => {
    const candidate = (handle || '').trim();
    if (candidate.length > USERNAME_QUERY_MAX_LENGTH) {
      return Promise.resolve({
        available: false,
        reason: 'Usernames must be at most 30 characters',
      });
    }
    return request(`/usernames/available?u=${encodeURIComponent(candidate)}`);
  },
  // D-7. Confirm-once: sets `username` and stamps `username_changed_at`, which
  // is what `username_confirmed` derives from and therefore what releases the
  // ChooseHandlePage gate. Resolves the updated account (same shape as `me`).
  // 403 means the handle was already confirmed — renaming is Part 2 (UN-8/UN-9);
  // 409 means taken or reserved, one body for both.
  confirmUsername: (handle) =>
    request('/auth/username', {
      method: 'POST',
      body: JSON.stringify({ username: (handle || '').trim() }),
    }),
  me: () => request('/auth/me'),
  // Display only: the database is always metric, so this cannot alter a single
  // stored quantity, which is why the UI applies it with no save step.
  setUnitSystem: (unitSystem) =>
    request('/auth/me/unit-system', {
      method: 'PUT',
      body: JSON.stringify({ unit_system: unitSystem }),
    }),
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
