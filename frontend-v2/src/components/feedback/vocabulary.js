// The feedback enumerations: each wire value, its words, and (for those shown
// as a Badge) its tone, in the order every control offers them. The one copy
// both the tester's dialog and the admin's triage screen read from.
//
// Tones: a type is a category, so it takes a category hue; a status runs from
// the neutral caramel (nothing decided yet) to the guide's positive forest
// (fixed), with sage -- the quieter green -- for set aside.

export const FEEDBACK_TYPES = [
  { value: 'issue', label: 'Issue', tone: 'terracotta' },
  { value: 'request', label: 'Request', tone: 'sky' },
  { value: 'improvement', label: 'Improvement', tone: 'teal' },
  { value: 'not_working', label: 'Not working', tone: 'danger' },
]

export const FEEDBACK_STATUSES = [
  { value: 'open', label: 'Open', tone: 'caramel' },
  { value: 'in_progress', label: 'In progress', tone: 'plum' },
  { value: 'closed_fixed', label: 'Closed: fixed', tone: 'forest' },
  { value: 'closed_ignored', label: 'Closed: ignored', tone: 'sage' },
]

export const FEEDBACK_PRIORITIES = [
  { value: 'low', label: 'Low' },
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'High' },
]

/** The entry for `value` in `table`, or undefined for a value it lacks. */
export const entryFor = (table, value) => table.find((entry) => entry.value === value)
