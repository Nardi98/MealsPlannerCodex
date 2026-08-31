/**
 * Translating between what the ingredient form shows and what is stored.
 *
 * The form asks for a density per 100 ml because that is the scale people can
 * estimate; storage keeps grams per millilitre. An empty box is stored as
 * null, never as a zero -- blank means "this measurement makes no sense for
 * this ingredient", which is a permanent answer and not a missing one.
 */

// Dividing by a hundred introduces binary-float noise (91.1 / 100 is not
// exactly 0.911), which would show up as drift the next time the form is
// opened. Six decimals is far finer than any density anyone will type.
const round6 = (n) => Math.round(n * 1e6) / 1e6

const numeric = (text) => {
  const value = Number(text)
  return text !== '' && Number.isFinite(value) && value > 0 ? value : null
}

/** The form's draft, as the API wants it stored. */
export function toConversions({ gramsPerPiece, gramsPer100Ml, preferredDimension }) {
  const perMl = numeric(gramsPer100Ml)
  return {
    grams_per_ml: perMl === null ? null : round6(perMl / 100),
    grams_per_piece: numeric(gramsPerPiece),
    preferred_dimension: preferredDimension || null,
  }
}

/** A stored ingredient, as the form wants it typed. */
export function fromConversions(ingredient) {
  return {
    gramsPerPiece:
      ingredient?.grams_per_piece == null ? '' : String(ingredient.grams_per_piece),
    gramsPer100Ml:
      ingredient?.grams_per_ml == null
        ? ''
        : String(round6(ingredient.grams_per_ml * 100)),
    preferredDimension: ingredient?.preferred_dimension || '',
  }
}
