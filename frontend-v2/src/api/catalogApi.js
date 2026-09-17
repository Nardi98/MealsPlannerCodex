import { request } from './client';
import { basisOf } from '../utils/servings';

// The system recipe catalog ("Discover", spec §10.1).
//
// Rows pass through unnormalised, like `sharedWithMeApi`: the backend builds
// them from an explicit field allowlist (API-7/8), and reshaping them here
// would create a second, drifting copy of that list. They are also kept out of
// `recipesApi` on purpose -- a catalog recipe is not in the user's book until
// it has been adopted.

// `course` and `tags` are repeatable keys (`?course=main&course=side`), which
// is why this appends rather than building the string from an object. Empty
// values are dropped so an unset filter is absent, not sent blank.
//
// Both listings share it: `status` is only meaningful to the admin one, and
// `courses`/`tags` only to the browse one, but an unset key costs nothing and
// one builder means one set of escaping rules.
function listQuery({ courses = [], tags = [], q, sort, status } = {}) {
  const params = new URLSearchParams();
  courses.forEach((course) => params.append('course', course));
  tags.forEach((tag) => params.append('tags', tag));
  if (q && q.trim()) params.append('q', q.trim());
  if (status) params.append('status', status);
  if (sort) params.append('sort', sort);
  const query = params.toString();
  return query ? `?${query}` : '';
}

const json = (method, body) => ({ method, body: JSON.stringify(body) });

/**
 * `NewRecipeModal`'s form shape → the admin routes' `RecipeWrite`.
 *
 * An allowlist, not a spread: the form is the user-book shape and carries
 * pantry ids, `favorite_side_ids` and conversion facts that mean nothing for a
 * system-owned recipe. Ingredients and tags go by NAME only -- the server
 * resolves them in the system account's namespace and rejects unknown names
 * (plan D3). `user_id` and `visibility` are never sent: ownership is the
 * server's to decide.
 */
export function toRecipeWrite(form) {
  return {
    title: form.title,
    course: form.course,
    servings: basisOf(form.servings),
    bulk_prep: Boolean(form.hot),
    procedure: form.procedure || '',
    image_url: form.image_url || null,
    tags: (form.tags || []).map((tag) => (tag.name ? tag.name : tag)),
    ingredients: (form.ingredients || [])
      .filter((ing) => (ing.name || '').trim())
      .map((ing) => ({
        name: ing.name,
        quantity: ing.amount === '' || ing.amount == null ? null : Number(ing.amount),
        unit: ing.unit || null,
      })),
  };
}

/**
 * The first thing the admin routes would reject in this form, as a sentence,
 * or null. Mirrors the server so a slip is named before any request: each
 * ingredient needs a positive quantity and a unit (a 422 otherwise), and a
 * name may appear once (the server's 400 `Duplicate ingredient: X`).
 */
export function recipeWriteProblem(form) {
  const seen = new Set();
  for (const { name, quantity, unit } of toRecipeWrite(form).ingredients) {
    if (!(quantity > 0) || !unit) return `"${name}" needs an amount and a unit.`;
    const key = name.trim().toLowerCase();
    if (seen.has(key)) return `Duplicate ingredient: ${name.trim()}`;
    seen.add(key);
  }
  return null;
}

/**
 * An API error as text a person can read. `client.request` only lifts a
 * string `detail` into the message; FastAPI's 422 carries an array of
 * `{loc, msg}` instead, which would otherwise surface as raw JSON.
 */
export function apiErrorText(err) {
  const detail = err?.data?.detail;
  if (!Array.isArray(detail)) return err.message;
  return detail
    .map(({ loc = [], msg }) => {
      // ['body', 'ingredients', 0, 'quantity'] → 'ingredient 1 quantity'
      const field = loc
        .filter((part) => part !== 'body')
        .map((part) => (typeof part === 'number' ? part + 1 : part === 'ingredients' ? 'ingredient' : part))
        .join(' ');
      return field ? `${field}: ${msg}` : msg;
    })
    .join('; ');
}

/** A catalog or admin row → the `initialRecipe` `NewRecipeModal` pre-fills from. */
export function toRecipeForm(row) {
  return {
    title: row.title,
    course: row.course,
    servings: basisOf(row.servings),
    hot: Boolean(row.bulk_prep),
    procedure: row.procedure || '',
    image_url: row.image_url || null,
    tags: row.tags || [],
    ingredients: (row.ingredients || []).map((ing) => ({
      id: undefined,
      name: ing.name,
      amount: ing.quantity,
      unit: ing.unit,
    })),
  };
}

const ADMIN = '/admin/catalog';

export const catalogApi = {
  // Published catalog recipes, filtered, searched and sorted server-side.
  list: (filters) => request(`/catalog/recipes${listQuery(filters)}`),

  // One published recipe, with its procedure (UI-7). 404 unless published.
  get: (recipeId) => request(`/catalog/recipes/${encodeURIComponent(recipeId)}`),

  // Copy recipes into the caller's book in one transaction
  // → { created_ids, skipped_ids }.
  adopt: (recipeIds) => request('/catalog/adopt', json('POST', { recipe_ids: recipeIds })),

  // Curation (spec §10.2). Every route is admin-only on the server (403
  // otherwise); the page only decides whether to show the controls.
  admin: {
    // Published AND retired entries, with status -- a separate endpoint from
    // `list`, which hides retired entries from admins too (RET-1, UI-16).
    // Searched, filtered by status and sorted server-side, like the browse one.
    list: (filters) => request(`${ADMIN}/recipes${listQuery(filters)}`),
    // Created published: a new catalog recipe is meant to be seen.
    create: (form) => request(`${ADMIN}/recipes`, json('POST', { ...toRecipeWrite(form), publish: true })),
    update: (recipeId, form) =>
      request(`${ADMIN}/recipes/${encodeURIComponent(recipeId)}`, json('PUT', toRecipeWrite(form))),
    publish: (recipeId) =>
      request(`${ADMIN}/recipes/${encodeURIComponent(recipeId)}/publish`, { method: 'POST' }),
    retire: (recipeId) =>
      request(`${ADMIN}/recipes/${encodeURIComponent(recipeId)}/retire`, { method: 'POST' }),
    // The whole catalog in pack-file shape (EXP-1..4).
    exportCatalog: () => request(`${ADMIN}/export`),
    // The system account's rows: the only names a catalog recipe may use (D3).
    ingredients: () => request(`${ADMIN}/ingredients`),
    tags: () => request(`${ADMIN}/tags`),
  },
};

export default catalogApi;
