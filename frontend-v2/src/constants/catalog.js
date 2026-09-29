// The system recipe catalog's shared vocabulary.

// The catalog's two server-side orderings (API-1). Each has one fixed
// direction, so the sort control shows no direction arrow. Both catalog screens
// offer the same two -- they are listing the same library, so a label that read
// differently on one of them would be a bug, not a variation. Each screen picks
// its own default: the browse grid leads with what other people added, the
// curation listing with the title a curator is looking for.
export const CATALOG_SORT_OPTIONS = [
  { value: 'popular', label: 'Most added' },
  { value: 'title', label: 'Title' },
]

// The staged-import item states that still want a human -- the same pair the
// server derives a batch's life from (`models.IMPORT_ITEM_OPEN_STATES`). Both
// import screens ask this question, so they ask it of one definition.
export const IMPORT_OPEN_STATES = ['pending', 'invalid']

export const isImportItemOpen = (item) => IMPORT_OPEN_STATES.includes(item?.state)
