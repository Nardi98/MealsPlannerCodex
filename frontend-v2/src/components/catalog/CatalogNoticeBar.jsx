import { XMarkIcon } from '@heroicons/react/24/outline'
import { IconButton } from '../IconButton'

/**
 * The bar both catalog screens report into: one `{ kind, text }` notice, plus
 * whatever actions the screen has to offer alongside it.
 *
 * `kind` is `'status'` or `'alert'` and doubles as the ARIA role, so the same
 * state that colours the text is the state that decides whether a screen
 * reader interrupts. `children` are the screen's actions (Discover's clear and
 * add buttons); with none, the dismiss control takes their place.
 *
 * Sticky and in the flow rather than fixed, so it never covers the last row of
 * whatever it sits under.
 */
export default function CatalogNoticeBar({ notice, onDismiss, children }) {
  return (
    <div
      className="sticky bottom-0 z-10 flex flex-wrap items-center gap-2 border bg-white p-3"
      style={{
        borderColor: 'var(--border-default)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-md)',
        marginBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      {notice && (
        <p
          role={notice.kind}
          className="min-w-0 flex-1"
          style={{
            margin: 0,
            fontSize: 'var(--text-sm)',
            color: notice.kind === 'alert' ? 'var(--c-neg)' : 'var(--text-strong)',
          }}
        >
          {notice.text}
        </p>
      )}
      {children || (
        <IconButton Icon={XMarkIcon} label="Dismiss" className="ml-auto" onClick={onDismiss} />
      )}
    </div>
  )
}
