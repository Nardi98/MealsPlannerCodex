import { Z } from '../lib/layers'

/**
 * The primary action of a page, floating in the bottom-right corner.
 *
 * 56px rather than the 44px floor: this is the one control a thumb goes for
 * without looking. It sits above `env(safe-area-inset-bottom)` so a home
 * indicator does not eat it, and below `Z.drawer` so the nav drawer and every
 * dialog still cover it.
 *
 * A page that renders one must pad the bottom of its scrolling content by at
 * least the button's height plus its offset, or the last row hides underneath.
 */
export default function Fab({ Icon, label, onClick, ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="fixed flex h-14 w-14 items-center justify-center rounded-full shadow-lg"
      style={{
        right: 16,
        bottom: 'calc(16px + env(safe-area-inset-bottom))',
        backgroundColor: 'var(--c-a2)',
        color: 'var(--text-on-accent)',
        zIndex: Z.drawer - 1,
      }}
      {...props}
    >
      {Icon && <Icon className="h-7 w-7" />}
    </button>
  )
}
