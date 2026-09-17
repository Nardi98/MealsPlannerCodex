import { Button } from '../Button'
import { mutedTextStyle } from './textStyles'

/**
 * What a catalog screen shows when its listing request failed: what could not
 * be loaded, and one way to ask again.
 *
 * `role="alert"` so the failure is announced rather than only seen, and the
 * retry is the screen's own reload -- neither page reaches for the browser's,
 * which would throw away everything else on screen.
 */
export default function CatalogLoadFailed({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <p role="alert" style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>
        {message}
      </p>
      <Button variant="ghost" onClick={onRetry}>
        Try again
      </Button>
    </div>
  )
}
