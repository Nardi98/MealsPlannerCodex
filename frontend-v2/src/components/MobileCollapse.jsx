import React from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'
import { useIsMobile } from '../hooks/useIsMobile'

// Folds a section away behind a toggle on a phone, and gets out of the way
// entirely on desktop — no wrapper, no button, the children as they were.
//
// One of the few places the breakpoint has to be a JS branch rather than a
// `md:` class: collapsed means *unmounted*, so a tall form costs nothing until
// it is asked for. `tourId` exists because of that — a tutorial step anchored
// inside the children has nothing to point at while they are gone, so the
// toggle carries the fallback anchor.
//
// `defaultOpen` is the caller's call: folding away is right for a section a
// visit rarely needs, wrong for one it usually came to use.
export default function MobileCollapse({ title, tourId, defaultOpen = false, children }) {
  const isMobile = useIsMobile()
  const [open, setOpen] = React.useState(defaultOpen)

  if (!isMobile) return children

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        data-tour={tourId}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex h-11 w-full items-center justify-between rounded-xl border px-4 text-sm font-bold"
        style={{ borderColor: 'var(--border-default)', color: 'var(--text-strong)' }}
      >
        {title}
        <ChevronDownIcon
          className="h-5 w-5 transition-transform"
          style={{ transform: open ? 'rotate(180deg)' : undefined }}
        />
      </button>
      {open && children}
    </div>
  )
}
