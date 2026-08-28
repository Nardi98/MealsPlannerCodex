/**
 * The servings basis: how many people a recipe's stored ingredient quantities
 * were written for.
 *
 * Quantities are stored exactly as authored, never rescaled, so every reader
 * that renders or sums them has to divide by this. The column is NOT NULL and
 * `>= 1` in the database, but recipes arrive here from imports, chatbot output
 * and typed-in forms as well as the API, so the normalisation lives in one
 * place rather than being guessed at each call site.
 */

// Anything absent, non-numeric or below one means "written for one person",
// which is what every recipe predating the basis meant.
export function basisOf(servings) {
  const n = Number(servings)
  return Number.isFinite(n) && n >= 1 ? Math.round(n) : 1
}

export const peopleLabel = (n) => (n === 1 ? 'person' : 'people')
