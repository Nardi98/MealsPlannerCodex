/**
 * The one place the app knows what a unit means.
 *
 * A quantity is a physical amount that happens to be written in one of several
 * equivalent ways; the unit is a *view* of it, not a property of it. Storage
 * holds only `g`, `ml` and `piece` -- one base unit per dimension -- and every
 * other unit the user may type or a chatbot may send is translated here, at the
 * edges, on the way in and on the way out.
 *
 * Conversion comes in two tiers:
 *
 *   Tier 1, within a dimension, is arithmetic: 1 cup is 236.6 ml for everyone,
 *   forever. It lives in the table below.
 *
 *   Tier 2, across dimensions, is ingredient-specific physics: ml -> g needs a
 *   density and piece -> g needs a piece weight. Those two numbers live on the
 *   ingredient, and where one is null the conversion is refused -- this module
 *   never invents a factor, not even water's density for an unknown liquid.
 */

// One base unit per dimension. These, and only these, are ever stored.
export const BASE_UNITS = { mass: 'g', volume: 'ml', piece: 'piece' }

/**
 * Tier 1: how many base units one of each unit is worth.
 *
 * Count-ish words map to a piece at 1:1 on purpose. A source saying "2 cloves"
 * means two countable things, and an accompanying piece weight is then per
 * clove, which is exactly right.
 */
const TIER_1 = {
  g: { dimension: 'mass', perBase: 1 },
  kg: { dimension: 'mass', perBase: 1000 },
  oz: { dimension: 'mass', perBase: 28.35 },
  lb: { dimension: 'mass', perBase: 453.6 },
  ml: { dimension: 'volume', perBase: 1 },
  l: { dimension: 'volume', perBase: 1000 },
  tsp: { dimension: 'volume', perBase: 4.93 },
  tbsp: { dimension: 'volume', perBase: 14.8 },
  cup: { dimension: 'volume', perBase: 236.6 },
  'fl oz': { dimension: 'volume', perBase: 29.57 },
  piece: { dimension: 'piece', perBase: 1 },
  clove: { dimension: 'piece', perBase: 1 },
  slice: { dimension: 'piece', perBase: 1 },
  bunch: { dimension: 'piece', perBase: 1 },
}

// The curated entry vocabulary, ordered so the user's usual units lead without
// the rest being hidden. `bunch` is accepted on import but not offered here --
// nobody buys a bunch of anything in a quantity field.
const METRIC_ORDER = [
  'g', 'kg', 'ml', 'l', 'piece',
  'oz', 'lb', 'tsp', 'tbsp', 'cup', 'fl oz', 'clove', 'slice',
]
const US_ORDER = [
  'oz', 'lb', 'cup', 'tbsp', 'tsp', 'fl oz',
  'piece', 'g', 'kg', 'ml', 'l', 'clove', 'slice',
]

export const UNIT_OPTIONS = (system) =>
  system === 'us' ? [...US_ORDER] : [...METRIC_ORDER]

/** The dimension a unit measures, or null when the unit is not one we know. */
export function dimensionOf(unit) {
  return TIER_1[unit]?.dimension ?? null
}

/**
 * Translate an amount written in any accepted unit into its base unit.
 *
 * Returns null for a unit outside the vocabulary rather than guessing at it. A
 * null amount stays null: an unquantified line is a real thing, and the unit it
 * was written in still tells us its dimension.
 */
export function toBaseUnit(amount, unit) {
  const entry = TIER_1[unit]
  if (!entry) return null

  const base = BASE_UNITS[entry.dimension]
  if (typeof amount !== 'number') return { amount: null, unit: base }
  return { amount: amount * entry.perBase, unit: base }
}

/** The reverse: render a base-unit amount in one of the units above it. */
export function fromBaseUnit(amount, unit) {
  const entry = TIER_1[unit]
  if (!entry) return null
  if (typeof amount !== 'number') return null
  return amount / entry.perBase
}

/**
 * A factor is usable only when it is a real, positive number, and null
 * otherwise. Zero is not a factor: crossing with it would produce 0 or
 * Infinity, both of them lies.
 */
export const asFactor = (value) =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null

/**
 * Convert an amount from one dimension into another using the ingredient's own
 * conversions, or return null when the required factor is not there.
 *
 * Volume to count (or back) is two hops through mass, which is why "1 cup of
 * flour" and "2 onions" are the same problem: both cross a dimension, and both
 * need a number only the ingredient can supply.
 *
 * Null is the honest answer, never a fallback number. Callers render what they
 * have and say plainly what they cannot derive.
 */
export function convert(amount, fromDimension, toDimension, ingredient) {
  if (typeof amount !== 'number' || !Number.isFinite(amount)) return null
  if (fromDimension === toDimension) return amount
  if (!ingredient) return null

  const density = asFactor(ingredient.grams_per_ml)
  const perPiece = asFactor(ingredient.grams_per_piece)

  // Everything routes through mass, the dimension both factors are stated in.
  let grams
  if (fromDimension === 'mass') grams = amount
  else if (fromDimension === 'volume') grams = density === null ? null : amount * density
  else grams = perPiece === null ? null : amount * perPiece
  if (grams === null) return null

  if (toDimension === 'mass') return grams
  if (toDimension === 'volume') return density === null ? null : grams / density
  return perPiece === null ? null : grams / perPiece
}

/**
 * Which of the three dimensions this ingredient can be expressed in.
 *
 * Drives the pantry badges, the "usually measured by" options, and the shopping
 * list's decision between one unified row and one row per dimension. An
 * ingredient reaching a single dimension is a normal ingredient, not a broken
 * one.
 */
export function reachableDimensions(ingredient) {
  const density = asFactor(ingredient?.grams_per_ml)
  const perPiece = asFactor(ingredient?.grams_per_piece)
  if (!density && !perPiece) return []

  const reached = ['mass']
  if (density) reached.push('volume')
  if (perPiece) reached.push('piece')
  return reached
}

// Round to 2 decimals, dropping floating-point noise (e.g. 0.333 * 3 -> 1).
export const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100

// The fractions worth spelling out; anything else falls back to a decimal.
// One map, shared by piece counts and by the batch label beside a meal.
export const FRACTIONS = { 0.25: '¼', 0.5: '½', 0.75: '¾' }

/**
 * Round a count to the nearest quarter, never down to nothing.
 *
 * A recipe needing a splash of onion still means buying an onion, so anything
 * above zero floors at a quarter. A genuine zero stays zero.
 *
 * The floor applies only to amounts that were positive to begin with. A
 * negative count is bad data, and rendering it as a quarter would hide the one
 * signal that something is wrong -- so it is passed through, rounded, and left
 * to read as the nonsense it is.
 */
export function roundPieces(amount) {
  if (typeof amount !== 'number' || !Number.isFinite(amount)) return null
  const rounded = Math.round(amount * 4) / 4
  if (amount <= 0) return rounded
  return Math.max(0.25, rounded)
}

/**
 * A count reads as a number and a fraction glyph: 1½, ¼, 2.
 *
 * Shared with the batch label beside a meal, so a fraction of a recipe and a
 * fraction of an onion are spelled the same way.
 */
export function formatCount(amount, round = roundPieces) {
  const rounded = round(amount)
  const whole = Math.floor(rounded)
  const fraction = FRACTIONS[round2(rounded - whole)]
  if (fraction) return `${whole || ''}${fraction}`
  return String(rounded)
}

// Where each dimension promotes to a larger unit, per system. Metric promotes
// at a thousand base units; US promotes at one pound and at one cup.
const PROMOTIONS = {
  metric: { mass: ['g', 'kg'], volume: ['ml', 'l'] },
  us: { mass: ['oz', 'lb'], volume: ['fl oz', 'cup'] },
}

/**
 * Render a stored base-unit amount the way this user reads amounts.
 *
 * Display only: the number handed in is the stored one, and nothing here ever
 * writes back. Returns null when there is no amount to render, so callers show
 * the ingredient name alone rather than a bare zero.
 */
export function formatAmount(amount, unit, system = 'metric') {
  if (typeof amount !== 'number' || !Number.isFinite(amount)) return null

  const dimension = dimensionOf(unit)
  if (dimension === 'piece') return `${formatCount(amount)} piece`

  const [small, large] = PROMOTIONS[system === 'us' ? 'us' : 'metric'][dimension]
  const target = amount >= TIER_1[large].perBase ? large : small
  return `${round2(fromBaseUnit(amount, target))} ${target}`
}

// Mass first: when nothing else decides, weighing it is the answer that works
// for the most ingredients.
export const DIMENSION_ORDER = ['mass', 'volume', 'piece']

// Amounts are rounded once, at the end, in the dimension they end up in.
// Rounding along the way would compound the error.
export const roundIn = (dimension, amount) =>
  dimension === 'piece' ? roundPieces(amount) : round2(amount)

/**
 * The factors an ingredient would need before these dimensions can be unified.
 *
 * Mass is the hub both factors are stated against, so a volume in the mix
 * needs a density and a count needs a piece weight. Returns only what is
 * actually absent, so an empty list means the dimensions already reconcile.
 */
export function missingFactorsFor(dimensions, ingredient) {
  const known = dimensions.filter((d) => DIMENSION_ORDER.includes(d))
  if (known.length < 2) return []

  return [
    known.includes('volume') && 'grams_per_ml',
    known.includes('piece') && 'grams_per_piece',
  ].filter((name) => name && asFactor(ingredient?.[name]) === null)
}

/**
 * Every other way this amount could be written down.
 *
 * Feeds the muted secondary beside a primary value, on the recipe page and in
 * the shopping list alike. Returns only what the ingredient's conversions
 * actually reach -- an empty list is the honest answer for an ingredient
 * nobody has taught the app anything about, and is not an error.
 */
export function alternateForms(amount, unit, ingredient) {
  const from = dimensionOf(unit)
  if (amount === null || from === null) return []

  return reachableDimensions(ingredient)
    .filter((to) => to !== from)
    .map((to) => {
      const converted = convert(amount, from, to, ingredient)
      return converted === null
        ? null
        : { amount: roundIn(to, converted), unit: BASE_UNITS[to] }
    })
    .filter(Boolean)
}
