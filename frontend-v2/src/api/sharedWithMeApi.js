import { request } from './client';

// "Shared with me" (§5.3) and the copy operation (§7.1).
//
// Deliberately no normalise/serialise layer: the backend already projects these
// recipes through `public_schema.PublicRecipe`, which is an *allowlist* (PRV-2).
// Reshaping the payload here would create a second, drifting copy of that field
// list; passing it through keeps the allowlist the single source of truth.
//
// These entries are kept out of `recipesApi` on purpose (SWM-5): a shared recipe
// must not reach the user's recipe list, planner candidates, or shopping list
// until it has been explicitly copied.
//
// Share tokens are never written to localStorage/sessionStorage and never
// logged. The only token this module sees is the one `SharedRecipePage` reads
// from the URL, and it is passed straight to the request.

export const sharedWithMeApi = {
  // Every live share addressed to the caller.
  fetchAll: () => request('/shared-with-me'),

  // One entry, by share id. 404 for anything that is not a live entry of the
  // caller's — revoked, expired, dismissed, or someone else's are deliberately
  // indistinguishable.
  fetchOne: (shareId) => request(`/shared-with-me/${encodeURIComponent(shareId)}`),

  // Copy the entry into the caller's own book → { id, title, already_copied }.
  copy: (shareId) =>
    request(`/shared-with-me/${encodeURIComponent(shareId)}/copy`, {
      method: 'POST',
    }),

  // Drop the entry from the caller's list only; the share itself is untouched.
  dismiss: (shareId) =>
    request(`/shared-with-me/${encodeURIComponent(shareId)}/dismiss`, {
      method: 'POST',
    }),

  // The `/shared/:token` landing route's copy. Used only there — the
  // "Shared with me" list holds no raw tokens (they are stored hashed), which
  // is exactly why the share-id keyed endpoints above exist.
  copyByToken: (token) =>
    request(`/s/${encodeURIComponent(token)}/copy`, { method: 'POST' }),
};

export default sharedWithMeApi;
