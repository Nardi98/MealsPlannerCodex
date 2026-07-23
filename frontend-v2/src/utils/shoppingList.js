import { format } from 'date-fns'

// Round to 2 decimals, dropping floating-point noise (e.g. 0.333 * 3 -> 1).
const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;

/**
 * Aggregate a shopping list from meal occurrences.
 *
 * Each item is one recipe instance (a meal's main dish, or one of its sides)
 * tagged with `people` — the number of people that meal is cooked for. Recipes
 * are authored for a single serving, so every ingredient amount is multiplied
 * by `people` before summing. A non-numeric amount stays `null` (shown without
 * a quantity), and any occurrence with a `null` amount makes the merged total
 * `null`. Summed amounts are rounded to 2 decimals.
 */
export function buildShoppingList(items = []) {
  const map = new Map();

  items.forEach(({ people = 1, ingredients = [] }) => {
    ingredients.forEach((ing) => {
      const name = (ing.name || '').trim();
      const unit = ing.unit || '';
      const key = name.toLowerCase() + '||' + unit;
      const amount =
        typeof ing.amount === 'number' ? ing.amount * people : null;

      if (map.has(key)) {
        const existing = map.get(key);
        if (existing.amount === null || amount === null) {
          existing.amount = null;
        } else {
          existing.amount += amount;
        }
      } else {
        map.set(key, { key, name, amount, unit });
      }
    });
  });

  for (const entry of map.values()) {
    if (entry.amount !== null) entry.amount = round2(entry.amount);
  }

  return Array.from(map.values());
}

export function formatExportText(shoppingItems, startDate, endDate) {
  const lines = shoppingItems.map(
    ({ name, amount, unit }) =>
      `• ${name}${
        amount !== null ? `: ${amount}${unit ? ` ${unit}` : ''}` : ''
      }`,
  )

  return [
    `Shopping List (${format(startDate, 'yyyy-MM-dd')} → ${format(
      endDate,
      'yyyy-MM-dd',
    )})`,
    '',
    ...lines,
  ].join('\n')
}
