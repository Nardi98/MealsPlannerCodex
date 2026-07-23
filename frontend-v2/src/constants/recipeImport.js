// Prompt-assisted recipe import. The app hands the user this prompt to paste
// into any chatbot along with a recipe URL/text; the chatbot returns the JSON
// shape documented below, which `parseImportedRecipe` validates and maps to the
// internal recipe shape used by NewRecipeModal.

export const COURSES = ['main', 'first-course', 'side']
export const UNITS = ['g', 'kg', 'l', 'ml', 'piece']

// Looser than the merge tool's default (0.8) so import surfaces more candidate
// matches for the user to confirm rather than making them hunt the full list.
export const IMPORT_SUGGESTION_THRESHOLD = 0.7

export const IMPORT_PROMPT = `You are helping me import a recipe into my meal planner.
Read the recipe I give you (a URL or pasted text) and reply with ONLY a JSON
object — no markdown, no commentary — matching exactly this shape:

{
  "title": "string",
  "course": "main | first-course | side",
  "procedure": "string, the preparation steps",
  "bulk_prep": false,
  "tags": ["lowercase", "keywords"],
  "ingredients": [
    { "name": "string", "quantity": 0, "unit": "g | kg | l | ml | piece", "season_months": [1,2,3] }
  ]
}

Rules:
- "course" must be one of: main, first-course, side.
- "unit" must be one of: g, kg, l, ml, piece.
- Scale every ingredient "quantity" to a SINGLE serving (one person).
- "quantity" must be a number; "season_months" is optional (numbers 1-12) and may be omitted.
- Output the JSON object and nothing else.`

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
    return { recipe: null, errors: ['Pasted text is not valid JSON.'] }
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
    return {
      id: undefined,
      name,
      amount: isFiniteNumber(ing?.quantity) ? ing.quantity : '',
      unit: ing?.unit ?? '',
      season_months: season,
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
