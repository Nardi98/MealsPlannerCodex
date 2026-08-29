// What covers the page, and in what order.
//
// A module of its own rather than constants hanging off `Modal.jsx`: the
// tutorial overlay and the nav drawer need the wash and the stacking order
// without needing the dialog, and a component file that also exports values
// cannot hot-reload.

// The dark wash behind anything that takes over the screen.
export const SCRIM = 'rgba(12,58,45,0.55)'

// The one stacking order. Previously each modal picked its own number and
// three of them disagreed.
export const Z = {
  // A page's floating action button: above the page, under everything that
  // covers it.
  fab: 50,
  drawer: 55,
  modal: 60,
  // A dialog raised from inside another one — a confirmation over a form.
  nested: 70,
}
