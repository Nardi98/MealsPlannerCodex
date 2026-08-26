// What each control on the plan-generation form actually does, in the user's
// terms. Kept next to the form rather than in the tour's step registry: this is
// help you ask for by hovering a setting, not a scripted walkthrough.
//
// The preset copy describes the real weights in `hooks/useGeneration.js`
// (LEFTOVER_PRESETS, SEASONALITY_PRESETS, RECENCY_PRESETS) — change one and the
// other must follow.
export const SETTING_HELP = {
  dates: {
    title: 'Plan dates',
    body: 'The stretch of days to fill. Generating over days that already have meals asks you before overwriting them.',
  },
  meals_per_day: {
    title: 'Meals per day',
    body: 'How many slots each day gets. Two means lunch and dinner; one plans a single main meal.',
    presets: [
      { value: 1, label: '1 meal', text: 'One main meal a day — a lighter plan and a shorter shopping list.' },
      { value: 2, label: '2 meals', text: 'Lunch and dinner, the usual full week.' },
    ],
  },
  epsilon: {
    title: 'Recommendation style',
    body: 'How often the planner picks something at random instead of the highest-scoring recipe. Towards Favorite food it sticks to what you rate well; towards Random selection it takes more chances, which is how new recipes get discovered.',
  },
  leftovers: {
    title: 'Leftovers',
    body: 'How much the plan leans on cooking once and eating twice. Recipes marked as bulk-prep get a bonus, and accepting one reserves nearby slots for the leftovers.',
    presets: [
      { value: 'fresh', label: 'Everything fresh', text: 'No leftovers at all — every meal is cooked on the day.' },
      { value: 'some', label: 'Some leftovers', text: 'A moderate bulk bonus, leftovers kept for up to 3 days.' },
      { value: 'lots', label: 'Cook in bulk', text: 'Double the bulk bonus, leftovers kept for up to 5 days — the least cooking.' },
    ],
  },
  seasonality: {
    title: 'Seasonality',
    body: 'How much a recipe being in season for the planned month counts in its score.',
    presets: [
      { value: 'ignore', label: "Don't care about seasons", text: 'Season is ignored entirely.' },
      { value: 'prefer', label: 'Prefer seasonal', text: 'In-season recipes get a normal nudge upwards.' },
      { value: 'strict', label: 'Strictly seasonal', text: 'Season counts triple, so out-of-season recipes rarely make the plan.' },
    ],
  },
  recency: {
    title: 'Variety',
    body: 'How hard recently-eaten recipes are pushed down the list. The penalty fades as time passes since you last ate something.',
    presets: [
      { value: 'low', label: 'Repeat freely', text: 'Half the usual penalty — favourites can come back quickly.' },
      { value: 'medium', label: 'Some variety', text: 'The standard penalty on anything eaten recently.' },
      { value: 'high', label: 'Maximise variety', text: 'Double the penalty, so the week spreads across as many recipes as possible.' },
    ],
  },
  avoid_tags: {
    title: 'Avoid tags',
    body: 'Recipes carrying any of these tags are left out of the plan completely — use it for allergies or a week off a whole category.',
  },
  reduce_tags: {
    title: 'Reduce tags',
    body: 'Softer than Avoid: recipes with these tags lose points but can still appear when they are the best fit.',
  },
  fridge: {
    title: 'Your Fridge',
    body: 'Ingredients you already have. Recipes that use them are favoured until the amount you listed is used up, so they get eaten before they go off.',
  },
}
