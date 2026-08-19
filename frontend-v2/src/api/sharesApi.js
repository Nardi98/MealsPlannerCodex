import { request } from './client';

// A blank field in the dialog means "not set". Sending '' would be validated as
// a malformed address / timestamp, so normalise it to null (SH-5, SH-9).
function blankToNull(value) {
  if (value === undefined || value === null) return null;
  const trimmed = String(value).trim();
  return trimmed === '' ? null : trimmed;
}

// <input type="date"> yields 'YYYY-MM-DD'; the API wants a datetime. Expiry is
// end-of-day local so a share picked for "the 1st" survives through the 1st.
function toIsoDateTime(value) {
  const raw = blankToNull(value);
  if (raw === null) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return new Date(`${raw}T23:59:59`).toISOString();
  }
  return raw;
}

export const sharesApi = {
  // Returns a ShareCreated whose `url` is the only time the raw token is ever
  // visible — it is unrecoverable afterwards, so callers must not persist it.
  create: (recipeId, { mode = 'link', recipient_email, expires_at } = {}) =>
    request(`/recipes/${recipeId}/shares`, {
      method: 'POST',
      body: JSON.stringify({
        mode: mode || 'link',
        recipient_email: blankToNull(recipient_email),
        expires_at: toIsoDateTime(expires_at),
      }),
    }),

  // SH-20 listing: same shape as create's response minus `url`.
  list: (recipeId) => request(`/recipes/${recipeId}/shares`),

  revoke: (shareId) => request(`/shares/${shareId}`, { method: 'DELETE' }),
};

export default sharesApi;
