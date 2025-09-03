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
