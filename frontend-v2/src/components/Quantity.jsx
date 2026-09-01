import { formatAmount } from '../utils/units'

/**
 * An amount, plus every equivalent way of writing it down.
 *
 * The primary value reads in normal weight and the alternates sit beside it,
 * smaller and muted. One component and one set of data serve every screen:
 * desktop keeps the alternates inline, mobile lets them wrap below, and that
 * is a CSS decision rather than a fork in the logic.
 *
 * Renders nothing at all when there is no amount, so a line whose quantity
 * nobody stated shows its name alone instead of a bare zero.
 */
export default function Quantity({ amount, unit, alternates = [], system }) {
  const primary = formatAmount(amount, unit, system)
  if (!primary) return null

  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <span>{primary}</span>
      {alternates.map((alternate) => {
        const rendered = formatAmount(alternate.amount, alternate.unit, system)
        return rendered ? (
          <span
            key={alternate.unit}
            className="text-xs"
            style={{ color: 'var(--text-subtle)' }}
          >
            ({rendered})
          </span>
        ) : null
      })}
    </span>
  )
}
