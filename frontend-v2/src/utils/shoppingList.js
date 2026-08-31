import { format } from 'date-fns'
import { basisOf } from './servings'
import {
  BASE_UNITS,
  DIMENSION_ORDER,
  alternateForms,
  convert,
  dimensionOf,
  formatAmount,
  formatCount,
  missingFactorsFor,
  reachableDimensions,
  round2,
  roundIn,
} from './units'

/**
 * How much of one recipe a meal actually cooks, as a label to show beside it.
 *
 * Quantities are stored for `servings` people, so a meal for `people` needs
 * `people / servings` of the recipe. Null at exactly one batch -- there is
 * nothing to point out when you cook the recipe as written.
 */
export function batchLabel(people, servings) {
  const factor = people / basisOf(servings)
  if (factor === 1) return null
  // A fraction of a recipe is spelled the way a fraction of an onion is, but
  // without the snap to quarters: a third of a batch is a third of a batch.
  return `×${formatCount(factor, round2)}`
}

// The bucket an unrecognised (or absent) unit falls into. It is deliberately
// not one of DIMENSION_ORDER: nothing converts into or out of it.
const UNKNOWN_DIMENSION = '__unknown__'

/**
 * Which dimension a row should lead with.
 *
 * The ingredient's own preference wins when its conversions can actually reach
 * it -- filling in a piece weight is what unlocks counting an ingredient, and
 * a preference nothing can reach is moot rather than an error. Otherwise the
 * recipes decide by weight of numbers, ties going to mass.
 */
function primaryDimension(entry, reachable, known) {
  if (entry.preferred && reachable.includes(entry.preferred)) {
    return entry.preferred
  }
  return [...known].sort((a, b) => {
    const counts =
      entry.byDimension.get(b).count - entry.byDimension.get(a).count
    if (counts !== 0) return counts
    return DIMENSION_ORDER.indexOf(a) - DIMENSION_ORDER.indexOf(b)
  })[0]
}

/**
 * Aggregate a shopping list from meal occurrences.
 *
 * Each item is one recipe instance (a meal's main dish, or one of its sides)
 * tagged with `people` -- the number of people that meal is cooked for -- and
 * `servings`, the number the recipe's quantities were written for. Every
 * ingredient amount is scaled by `people / servings` before summing.
 *
 * The merge key is the *ingredient*, not the ingredient and its unit. Two
 * recipes disagreeing about whether an onion is counted or weighed are not two
 * things to buy, and the conversions on the ingredient are what let this say
 * so. Where they are missing the entry splits into one row per dimension, each
 * flagged with the factor that would unify them: the app says what it cannot
 * derive rather than guessing at it.
 */
export function buildShoppingList(items = []) {
  const entries = new Map()

  items.forEach(({ people = 1, servings, ingredients = [] }) => {
    const scale = people / basisOf(servings)
    ingredients.forEach((ing) => {
      const name = (ing.name || '').trim()
      const key = ing.id != null ? `#${ing.id}` : name.toLowerCase()
      const dimension = dimensionOf(ing.unit) ?? UNKNOWN_DIMENSION
      const amount = typeof ing.amount === 'number' ? ing.amount * scale : null

      if (!entries.has(key)) {
        entries.set(key, {
          key,
          id: ing.id ?? null,
          name,
          preferred: null,
          grams_per_ml: null,
          grams_per_piece: null,
          byDimension: new Map(),
        })
      }
      const entry = entries.get(key)
      // The first line to state a factor teaches the whole entry; later lines
      // for the same ingredient carry the same numbers.
      entry.grams_per_ml ??= ing.grams_per_ml ?? null
      entry.grams_per_piece ??= ing.grams_per_piece ?? null
      entry.preferred ??= ing.preferred_dimension ?? null

      const bucket = entry.byDimension.get(dimension) || { total: 0, count: 0 }
      bucket.total =
        bucket.total === null || amount === null ? null : bucket.total + amount
      bucket.count += 1
      entry.byDimension.set(dimension, bucket)
    })
  })

  return [...entries.values()].flatMap(toRows)
}

function toRows(entry) {
  const dimensions = [...entry.byDimension.keys()]
  const known = dimensions.filter((d) => d !== UNKNOWN_DIMENSION)
  const hasUnknown = known.length !== dimensions.length
  const reachable = reachableDimensions(entry)
  const identity = { key: entry.key, id: entry.id, name: entry.name }

  // Everything the recipes used can be restated in one dimension: one row.
  // Reachability is set membership, so there is nothing to compute here. An
  // unrecognised unit can never join that row -- there is no factor that
  // reaches a dimension we cannot name -- so its presence forces the split.
  const primary = primaryDimension(entry, reachable, known)
  const unifiable =
    !hasUnknown &&
    known.every((d) => d === primary || reachable.includes(d))

  if (unifiable) {
    const total = known.reduce((sum, d) => {
      const subtotal = entry.byDimension.get(d).total
      if (sum === null || subtotal === null) return null
      return sum + (d === primary ? subtotal : convert(subtotal, d, primary, entry))
    }, 0)

    const amount = total === null ? null : roundIn(primary, total)
    return [
      {
        ...identity,
        rowKey: entry.key,
        signature: String(amount),
        amount,
        unit: BASE_UNITS[primary] ?? '',
        alternates: alternateForms(total, BASE_UNITS[primary], entry),
        missing: [],
      },
    ]
  }

  // Otherwise the entry honestly spans two dimensions. One row each, both
  // carrying the ingredient's identity so they tick off together, and both
  // flagged with the factor that would close the gap.
  const missing = missingFactorsFor(known, entry)
  // The unknown bucket sorts last, but it is always emitted: an amount the app
  // cannot place is still an amount the user has to buy.
  const split = [
    ...DIMENSION_ORDER.filter((d) => entry.byDimension.has(d)),
    ...(hasUnknown ? [UNKNOWN_DIMENSION] : []),
  ]
  const amounts = split.map((d) => {
    const { total } = entry.byDimension.get(d)
    return total === null ? null : roundIn(d, total)
  })

  // One signature across the whole ingredient, so its rows tick and untick
  // together: the user is buying one thing, however many ways it is measured.
  const signature = amounts.join('/')
  return split.map((d, i) => ({
    ...identity,
    rowKey: `${entry.key}||${d}`,
    signature,
    amount: amounts[i],
    unit: BASE_UNITS[d] ?? '',
    alternates: [],
    missing,
  }))
}

export function formatExportText(shoppingItems, startDate, endDate, system) {
  // The primary value only. A pasted list should read like a list, not like a
  // conversion table.
  const lines = shoppingItems.map(({ name, amount, unit }) => {
    const rendered = formatAmount(amount, unit, system)
    return `• ${name}${rendered ? `: ${rendered}` : ''}`
  })

  return [
    `Shopping List (${format(startDate, 'yyyy-MM-dd')} → ${format(
      endDate,
      'yyyy-MM-dd',
    )})`,
    '',
    ...lines,
  ].join('\n')
}
