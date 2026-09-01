import { UNIT_OPTIONS, formatAmount, toBaseUnit } from '../utils/units'

/**
 * The unit a recipe line is being written in, with a live echo of what it
 * will be stored as.
 *
 * Two things make the normalisation honest rather than surprising. The
 * dropdown accepts what people actually write -- cups, ounces, cloves -- so
 * nobody has to do arithmetic before typing. And typing `1 cup` shows
 * `= 236.6 ml` beside the field as it is typed, so the user sees the
 * conversion happen and can correct the unit before saving.
 *
 * That echo is what makes the round trip acceptable: reopening the recipe
 * shows `236.6 ml`, not `1 cup`, because the source unit is deliberately not
 * stored. They already watched the conversion and agreed to it.
 */
export default function UnitField({ amount, unit, system, onChange, id = 'unit' }) {
  const parsed = Number(amount)
  const base =
    amount !== '' && Number.isFinite(parsed) ? toBaseUnit(parsed, unit) : null
  const echo =
    base && base.unit !== unit ? formatAmount(base.amount, base.unit, system) : null

  return (
    <span className="inline-flex items-center gap-2">
      <label className="sr-only" htmlFor={id}>
        Unit
      </label>
      <select
        id={id}
        value={unit}
        onChange={(e) => onChange({ amount, unit: e.target.value })}
        className="rounded-xl border px-2 py-1 text-sm"
        style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
      >
        {UNIT_OPTIONS(system).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {echo && (
        <span className="text-xs" style={{ color: 'var(--text-subtle)' }}>
          = {echo}
        </span>
      )}
    </span>
  )
}
