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

export function formatExportText(shoppingItems, crossed, startDate, endDate) {
  const openItems = shoppingItems
    .filter((i) => !crossed.has(i.id))
    .map((i) => `• ${i.label}`)

  return [
    `Shopping List (${format(startDate, 'yyyy-MM-dd')} → ${format(
      endDate,
      'yyyy-MM-dd',
    )})`,
    '',
    ...openItems,
  ].join('\n')
}
