/** `list` with `value` removed if present, appended if not. Never mutates `list`. */
export const toggleIn = (list, value) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
