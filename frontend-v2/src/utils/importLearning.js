import { round2 } from './units'

/**
 * What an import teaches the pantry, and how to say it back.
 *
 * Knowledge accumulates without being asked for: every import fills in a
 * conversion the pantry lacked, permanently and for free, and the user never
 * fills in a form to make that happen. Two rules govern it, and they are the
 * same rule stated twice:
 *
 *   the database wins -- a stored factor is the user's and is never replaced;
 *   absent is not wrong -- an omitted factor means "this dimension does not
 *   apply", is recorded as null, and is never invented.
 */

const FACTORS = ['grams_per_piece', 'grams_per_ml']

/**
 * The conversions worth writing onto `stored` from an imported `reply`.
 *
 * Returns only genuinely new facts, so an empty object means the import had
 * nothing to add -- which is the common case and not a failure.
 */
export function backfillFor(stored, reply) {
  const learned = {}
  for (const factor of FACTORS) {
    if (stored?.[factor] == null && reply?.[factor] != null) {
      learned[factor] = reply[factor]
    }
  }
  return learned
}

/**
 * The quiet receipt shown in the review step.
 *
 * Informational, dismissible, and blocking nothing. Its purpose is to make the
 * accumulation visible -- so the user understands why imports keep getting
 * better -- and to give them a chance to catch an obviously wrong number
 * without ever being required to look.
 */
export function learnedFacts(learned) {
  return learned.flatMap(({ name, grams_per_piece, grams_per_ml }) => {
    const facts = []
    if (grams_per_piece != null) {
      facts.push(`${name} ≈ ${round2(grams_per_piece)} g each`)
    }
    if (grams_per_ml != null) {
      // Per 100 ml, the scale people can actually picture.
      facts.push(`${name} ≈ ${round2(grams_per_ml * 100)} g per 100 ml`)
    }
    return facts
  })
}
