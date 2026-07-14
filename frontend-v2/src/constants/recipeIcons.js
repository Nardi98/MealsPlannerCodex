// Dish-type iconography for recipes. Heroicons has no food glyphs, so these
// borrow Material Design Icons (rendered via the Iconify set in Icon.jsx).

export const COURSE_ICONS = {
  main: 'silverware-fork-knife',
  side: 'bowl-mix-outline',
  'first-course': 'pot-steam-outline',
  dessert: 'cupcake',
}

// Course → category color variable, used to tint the dish chip and the
// placeholder tile shown when a recipe has no image.
export const courseColor = {
  main: 'var(--cat-terracotta)',
  side: 'var(--cat-olive)',
  'first-course': 'var(--cat-sky)',
  dessert: 'var(--cat-berry)',
}

// Keyword-based override so a specific dish (e.g. a pasta bowl) gets a more
// precise glyph than its generic course would imply.
const DISH_KEYWORDS = [
  [/pasta|noodle/i, 'noodles'],
  [/soup|stew/i, 'pot-steam-outline'],
  [/salad/i, 'leaf'],
  [/sandwich|toast/i, 'baguette'],
]

export function dishIcon(recipe) {
  const hit = DISH_KEYWORDS.find(([re]) => re.test(recipe.title || ''))
  return (hit && hit[1]) || COURSE_ICONS[recipe.course] || 'silverware-fork-knife'
}
