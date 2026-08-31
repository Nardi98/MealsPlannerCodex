// Prompt-assisted recipe import. The app hands the user this prompt to paste
// into any chatbot along with a recipe URL/text; the chatbot returns the JSON
// shape documented below, which `parseImportedRecipe` validates and maps to the
// internal recipe shape used by NewRecipeModal.

export const COURSES = ['main', 'first-course', 'side']

// Looser than the merge tool's default (0.8) so import surfaces more candidate
// matches for the user to confirm rather than making them hunt the full list.
export const IMPORT_SUGGESTION_THRESHOLD = 0.7

import { basisOf } from '../utils/servings'
import { UNIT_OPTIONS, toBaseUnit } from '../utils/units'

// What a chatbot may write a quantity in. The curated entry vocabulary plus
// the count-ish words a recipe actually uses, all of which normalise to a
// piece -- so a stated `grams_per_piece` is per clove, which is correct.
export const UNITS = [...UNIT_OPTIONS('metric'), 'bunch']

export const IMPORT_PROMPT = `You are helping me import a recipe into my meal planner.
Read the recipe I give you (a URL or pasted text) and reply with ONLY a JSON
object — no markdown, no commentary — matching exactly this shape:

{
  "title": "string",
  "course": "main | first-course | side",
  "procedure": "string, the preparation steps",
  "bulk_prep": false,
  "servings": 1,
  "tags": ["lowercase", "keywords"],
  "ingredients": [
    {
      "name": "string",
      "quantity": 0,
      "unit": "${UNITS.join(' | ')}",
      "grams_per_ml": 0.53,
      "grams_per_piece": 150,
      "season_months": [1,2,3]
    }
  ]
}

Rules:
- "course" must be one of: main, first-course, side.
- "unit" must be one of: ${UNITS.join(', ')}. Use whatever unit the recipe
  itself uses. Do NOT convert between units -- my app does that.
- "grams_per_ml" and "grams_per_piece" describe the *ingredient*, not this
  recipe: what 1 ml of it weighs, and what one of them weighs. Give them where
  they are meaningful and OMIT them where they are not -- flour has no piece
  weight, milk has no piece weight, an egg has no useful density. Omitting one
  is a correct answer. Never guess a number to fill a gap.
- For a count-ish unit (clove, slice, bunch), "grams_per_piece" is the weight
  of one of those, so per clove rather than per bulb.
- Copy every ingredient "quantity" EXACTLY as the recipe states it. Never scale
  or divide them.
- "servings" is how many people the recipe as written feeds. Use the number the
  source states; if it states none, use 1.
- "quantity" must be a number; "season_months" is optional (numbers 1-12) and may be omitted.

If you cannot read a recipe from what I gave you -- the page is unreachable or
behind a login, it is not a recipe, or the ingredients are unusable -- do NOT
invent one. Reply instead with one plain sentence saying why: no JSON, no
braces, no markdown, just the sentence.`

// A factor is only usable when it is a real, positive number; anything else
// is no answer at all, and null is the honest way to record that.
const positive = (value) =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null

// The longest chatbot sentence the modal's error list can show without the
// dialog turning into a wall of text.
const MAX_REASON = 300

/**
 * Read a reply that is not JSON.
 *
 * The prompt tells the chatbot to answer a recipe it cannot read with one plain
 * sentence saying why, so prose is a real answer and is shown as-is. A reply
 * that was *meant* to be the JSON object -- a stray markdown fence, a truncated
 * brace -- is a formatting slip rather than the chatbot explaining itself, and
 * saying "not valid JSON" is the more useful thing to tell the reader.
 */
function asChatbotReason(raw) {
  const text = String(raw).trim()
  if (!text || /^[[{`]/.test(text)) return 'Pasted text is not valid JSON.'
  return text.length > MAX_REASON
    ? `${text.slice(0, MAX_REASON - 1)}…`
    : text
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

/**
 * Parse the JSON a chatbot returned into the internal recipe shape consumed by
 * NewRecipeModal. Returns `{ recipe, errors }`; `recipe` is null when `errors`
 * is non-empty.
 */
export function parseImportedRecipe(raw) {
  let data
  try {
    data = JSON.parse(raw)
  } catch {
    return { recipe: null, errors: [asChatbotReason(raw)] }
  }

  const errors = []
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { recipe: null, errors: ['Expected a JSON object describing one recipe.'] }
  }

  const title = typeof data.title === 'string' ? data.title.trim() : ''
  if (!title) errors.push('A non-empty "title" is required.')

  const course = data.course ?? 'main'
  if (!COURSES.includes(course)) {
    errors.push(`"course" must be one of: ${COURSES.join(', ')}.`)
  }

  // How many people the quantities above are written for. A source that states
  // no head-count, or a nonsense one, is read as written for one person.
  const servings = basisOf(data.servings)

  const rawIngredients = Array.isArray(data.ingredients) ? data.ingredients : []
  const ingredients = rawIngredients.map((ing, i) => {
    const label = `Ingredient ${i + 1}`
    const name = typeof ing?.name === 'string' ? ing.name.trim() : ''
    if (!name) errors.push(`${label}: a "name" is required.`)
    if (!isFiniteNumber(ing?.quantity)) {
      errors.push(`${label}: "quantity" must be a number.`)
    }
    if (ing?.unit != null && !UNITS.includes(ing.unit)) {
      errors.push(`${label}: "unit" must be one of ${UNITS.join(', ')}.`)
    }
    const season = Array.isArray(ing?.season_months) ? ing.season_months : []

    // Normalise at the door: whatever the source wrote it in becomes the base
    // unit of its dimension, which is the only vocabulary storage accepts.
    const quantity = isFiniteNumber(ing?.quantity) ? ing.quantity : ''
    const base = ing?.unit ? toBaseUnit(quantity === '' ? null : quantity, ing.unit) : null

    return {
      id: undefined,
      name,
      amount: base ? (base.amount ?? '') : quantity,
      unit: base ? base.unit : '',
      season_months: season,
      // An absent conversion is a statement that the dimension does not apply.
      // It is recorded as null and never invented.
      grams_per_ml: positive(ing?.grams_per_ml),
      grams_per_piece: positive(ing?.grams_per_piece),
    }
  })

  if (data.tags != null && !Array.isArray(data.tags)) {
    errors.push('"tags" must be a list of strings.')
  }
  const tags = Array.isArray(data.tags)
    ? data.tags.filter((t) => typeof t === 'string')
    : []

  if (errors.length) return { recipe: null, errors }

  return {
    recipe: {
      title,
      course,
      servings,
      procedure: typeof data.procedure === 'string' ? data.procedure : '',
      hot: Boolean(data.bulk_prep),
      image_url: null,
      tags,
      ingredients,
      favorite_side_ids: [],
    },
    errors: [],
  }
}
