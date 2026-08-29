import { Button } from './Button'

/**
 * The running commentary for the two-step position swap.
 *
 * Arming a cell used to be signalled by a yellow tint and nothing else — no
 * text, no way out except pressing the same cell again, which nobody guesses.
 * This banner names the meal being moved and offers an explicit Cancel, and is
 * sticky so it stays on screen while you scroll to the target.
 */
export default function SwapBanner({ recipe, onCancel }) {
  return (
    <div
      role="status"
      data-testid="swap-banner"
      className="sticky top-0 z-10 mb-2 flex flex-wrap items-center justify-between gap-2 px-3 py-2"
      style={{
        backgroundColor: 'color-mix(in srgb, var(--c-a2) 22%, white)',
        border: '1px solid var(--c-a2)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--text-strong)',
      }}
    >
      <span className="min-w-0 text-sm">
        Swapping <strong>{recipe || 'this meal'}</strong> — pick another meal to
        exchange it with.
      </span>
      <Button variant="ghost" size="sm" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  )
}
