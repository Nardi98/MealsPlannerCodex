// The admin side of user feedback: triage of what testers sent in. Not to be
// confused with `feedbackApi`, which is the meal plan's accept/reject signal.
//
// Rows pass through unnormalised, like `catalogApi` and `alphaApi`: the backend
// builds them from an explicit field allowlist, and reshaping them here would
// create a second, drifting copy of it. The error-copy helpers live in
// `catalogApi` and the page imports them from there.
import { request, requestBlob } from './client';

const BASE = '/admin/feedback';
const json = (method, body) => ({ method, body: JSON.stringify(body) });
const item = (id) => `${BASE}/${encodeURIComponent(id)}`;

/** `?status=open&tag=mobile` from whichever filters are set; '' when none are. */
function queryString(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.append(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

export const userFeedbackAdminApi = {
  // Filters: status, type, priority, tag (a name), seen (boolean). They compose.
  list: (filters) => request(`${BASE}${queryString(filters)}`),
  unseenCount: () => request(`${BASE}/unseen-count`),
  get: (id) => request(item(id)),
  // Any subset of status, priority, admin_notes (null clears), tags (the whole
  // new set of names; unknown ones are created) and seen.
  update: (id, patch) => request(item(id), json('PATCH', patch)),
  listTags: () => request(`${BASE}/tags`),
  renameTag: (id, name) => request(`${BASE}/tags/${encodeURIComponent(id)}`, json('PATCH', { name })),
  // Bytes, not JSON, and admin-only: see `requestBlob` for why not a plain image URL.
  screenshot: (id) => requestBlob(`${item(id)}/screenshot`),
};

export default userFeedbackAdminApi;
