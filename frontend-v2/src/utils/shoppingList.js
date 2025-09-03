import { format } from 'date-fns'

export function buildShoppingList(recipes = []) {
  const map = new Map();

  recipes.forEach((r) => {
    (r.ingredients || []).forEach((ing) => {
      const name = (ing.name || '').trim();
      const unit = ing.unit || '';
      const key = name.toLowerCase() + '||' + unit;
      const amount = typeof ing.amount === 'number' ? ing.amount : null;

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
