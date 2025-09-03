import { format } from 'date-fns'

export function buildShoppingList(recipes = []) {
  const map = new Map();
  recipes.forEach((r) => {
    (r.ingredients || []).forEach((ing) => {
      const name = (ing.name || '').trim();
      const key = name.toLowerCase();
      if (!map.has(key)) {
        map.set(key, { key, name });
      }
    });
  });
  return Array.from(map.values());
}

export function formatExportText(shoppingItems, startDate, endDate) {
  const lines = shoppingItems.map((i) => `• ${i.label}`)

  return [
    `Shopping List (${format(startDate, 'yyyy-MM-dd')} → ${format(
      endDate,
      'yyyy-MM-dd',
    )})`,
    '',
    ...lines,
  ].join('\n')
}
