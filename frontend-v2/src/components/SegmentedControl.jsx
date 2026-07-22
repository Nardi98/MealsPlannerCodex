import React from 'react'

/**
 * A three-option "sliding selector": a segmented control where each option is a
 * column of icon-over-two-line-label, and the only selection cue is a mustard
 * underline bar that eases beneath the active tab (spec variant 1B).
 *
 * The bar is the single stateful part — labels never bold or recolor. Motion is
 * limited to the bar's `translateX`, and honors `prefers-reduced-motion`.
 *
 * Props:
 *  - `label`: caption shown above the row (also the tablist's accessible name).
 *  - `options`: `[{ value, label, sub, icon }]` where `label`/`sub` are the two
 *    label lines and `icon` is a rendered node (Heroicon `.seg-svg` or an
 *    `<img className="segu-ico" />` for the custom bulk/leftovers glyphs).
 *  - `value`: the currently selected option value.
 *  - `onChange(value)`: called with the chosen option's value.
 */
export default function SegmentedControl({ label, options, value, onChange }) {
  const btnRefs = React.useRef([])
  const selectedIndex = Math.max(
    0,
    options.findIndex((opt) => opt.value === value)
  )

  const move = (index) => {
    const next = (index + options.length) % options.length
    onChange(options[next].value)
    btnRefs.current[next]?.focus()
  }

  const onKeyDown = (event, index) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault()
      move(index + 1)
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault()
      move(index - 1)
    }
  }

  // Each tab is one bar-width plus the 4px gap wide, so stepping the bar by
  // (bar width + 4px) per index keeps it centered on the selected tab.
  const barStyle = {
    width: `calc((100% - ${(options.length - 1) * 4}px) / ${options.length})`,
    transform: `translateX(calc(${selectedIndex} * (100% + 4px)))`,
  }

  return (
    <div className="flex flex-col text-sm">
      {label && <span className="mb-2 font-bold text-base">{label}</span>}
      <div className="segu w-3/4 self-center" role="tablist" aria-label={label}>
        <div className="segu-track" aria-hidden="true" />
        <div className="segu-bar" style={barStyle} aria-hidden="true" />
        {options.map((opt, index) => {
          const active = index === selectedIndex
          return (
            <button
              key={opt.value}
              ref={(el) => (btnRefs.current[index] = el)}
              type="button"
              role="tab"
              aria-selected={active}
              tabIndex={active ? 0 : -1}
              aria-label={opt.sub ? `${opt.label} ${opt.sub}` : opt.label}
              onClick={() => onChange(opt.value)}
              onKeyDown={(e) => onKeyDown(e, index)}
              className="segu-btn"
            >
              {opt.icon}
              <span className="seg-lbl">
                {opt.label}
                {opt.sub && (
                  <>
                    <br />
                    {opt.sub}
                  </>
                )}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
