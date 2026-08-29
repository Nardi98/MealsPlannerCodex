// What each page's tour says, in the order it says it.
//
// Each step names its anchor by a `data-tour` attribute rather than a class or
// a label, so restyling or retranslating a page cannot silently break the
// tutorial — and so it is obvious in the page source that something points here.
//
// `placement` is a preference: the bubble flips to the opposite side when the
// preferred one has no room (see placement.js).
//
// A `target` may be a list of selectors in priority order. The steps that talk
// about a collection point at one member of it — one recipe card, one meal cell
// — because a bubble cannot sit beside a container taller than the window, and
// fall back to the container for the pages where that member does not exist yet
// (an empty recipe book, a week with no plan). See findTarget in useTour.js.

export const RECIPES_STEPS = [
  {
    target: ['[data-tour="recipes-card"]', '[data-tour="recipes-grid"]'],
    title: 'Your recipe book',
    body: 'Every recipe you have lives here. Click any card to see it, edit it, or share it with a friend.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="recipes-new"]',
    title: 'Add a recipe',
    body: 'Write one in yourself: a title, its ingredients, and when it is in season. The planner learns from what you add.',
    placement: 'bottom',
  },
  {
    // Below md this anchor lives inside the add sheet, which is unmounted
    // while the sheet is closed; the FAB that opens it is the fallback.
    target: ['[data-tour="recipes-import"]', '[data-tour="recipes-new"]'],
    title: 'Or let a chatbot do the typing',
    body: 'Copy the prompt you get here into any chatbot, along with the recipe, and paste back the JSON it returns — ingredients and all.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="recipes-search"]',
    title: 'Find anything fast',
    body: 'Search by title as you type.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="recipes-filter"]',
    title: 'Narrow it down',
    body: 'Filter by course, tag, or an ingredient you already have in the fridge.',
    placement: 'bottom',
  },
]

export const MEAL_PLAN_STEPS = [
  {
    target: ['[data-tour="mealplan-cell"]', '[data-tour="mealplan-calendar"]'],
    title: 'Your week, two meals a day',
    body: 'Each cell is a meal. Click one to accept it, reject it, swap it for something else, or add a side dish.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="mealplan-week-nav"]',
    title: 'Move between weeks',
    body: 'Plan ahead, or look back at what you ate.',
    placement: 'bottom',
  },
  {
    target: [
      '[data-tour="mealplan-tabs"]',
      '[data-tour="mealplan-form"]',
      '[data-tour="mealplan-settings-toggle"]',
    ],
    title: 'Tell the planner what you want',
    body: 'Pick the dates, lean on a tag, avoid an ingredient, or plan around what is already in your fridge.',
    placement: 'top',
  },
  {
    target: ['[data-tour="mealplan-generate"]', '[data-tour="mealplan-settings-toggle"]'],
    title: 'Then let it plan',
    body: 'Recipes are scored on what you like, the season, and how recently you ate them — accepting and rejecting meals teaches it.',
    placement: 'top',
  },
]

export const INGREDIENTS_STEPS = [
  {
    target: ['[data-tour="ingredients-group"]', '[data-tour="ingredients-list"]'],
    title: 'Everything your recipes are made of',
    body: 'Ingredients are grouped by category. Collapse a group you rarely look at — it stays that way.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="ingredients-new"]',
    title: 'Add an ingredient',
    body: 'Give it a category and the months it is in season. Seasonality is what makes the planner favour it at the right time of year.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="ingredients-months"]',
    title: 'See what is in season',
    body: 'Filter the list down to what is good this month.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="ingredients-merge"]',
    title: 'Tidy up duplicates',
    body: 'Ended up with "tomato" and "tomatoes"? Merge them and every recipe follows.',
    placement: 'bottom',
  },
]

// The registry: the one place that says which tours exist and what each one
// says. `PageTour` looks its steps up here by id, and `tourStorage` derives the
// list it silences from the same object — so adding a tour is one edit.
export const TOURS = {
  recipes: RECIPES_STEPS,
  'meal-plan': MEAL_PLAN_STEPS,
  ingredients: INGREDIENTS_STEPS,
}
