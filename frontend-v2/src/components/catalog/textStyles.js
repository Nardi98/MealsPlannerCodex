// Text styles shared by the Discover page, its detail view and the admin
// listing (and the Recipes detail view's section headings), plus the form
// label and help text of the share and feedback dialogs.

export const sectionHeadingStyle = {
  fontSize: 'var(--text-sm)',
  fontWeight: 'var(--weight-semibold)',
  marginBottom: 6,
  color: 'var(--text-strong)',
}

export const mutedTextStyle = { margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-subtle)' }

/** A form field's `<label>`, set on its own line above the control. */
export const fieldLabelStyle = {
  display: 'block',
  fontSize: 'var(--text-sm)',
  fontWeight: 'var(--weight-semibold)',
  color: 'var(--text-strong)',
  marginBottom: 4,
}

/** A field's help line. No margin: each dialog spaces it to its own layout. */
export const fieldHelpStyle = {
  fontSize: 'var(--text-xs)',
  color: 'var(--text-muted)',
  lineHeight: 1.4,
}
