// ALPHA-GATE: the closed-alpha signup allowlist. Deleted whole when the alpha
// ends (docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md).
//
// Rows pass through unnormalised, like `catalogApi`: the backend builds them
// from an explicit field allowlist, and reshaping them here would create a
// second, drifting copy of it. The error-copy helpers are not defined here
// either: they live in `catalogApi` and the page imports them from there, so
// the alpha screen reads like every other admin screen.
import { request } from './client';

const BASE = '/admin/alpha/invites';
const json = (method, body) => ({ method, body: JSON.stringify(body) });

export const alphaApi = {
  list: () => request(BASE),
  // One free-text field: newline/comma separated addresses. The server splits,
  // validates and partitions them into added / skipped_duplicates / invalid.
  add: (emails) => request(BASE, json('POST', { emails })),
  // An explicit null clears the note; the email is never editable.
  updateNote: (id, note) => request(`${BASE}/${encodeURIComponent(id)}`, json('PATCH', { note })),
  remove: (id) => request(`${BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

export default alphaApi;
