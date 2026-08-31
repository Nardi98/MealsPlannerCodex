import { Input } from './'
import { reachableDimensions } from '../utils/units'
import { toConversions } from '../utils/conversionDraft'

/**
 * How an ingredient converts, asked in plain language.
 *
 * Two numbers cover every case: what one of them weighs, and what a volume of
 * it weighs. Both are optional and both start empty, because **blank is a
 * legitimate, permanent answer** -- milk has no piece weight, eggs have no
 * useful density -- and never an outstanding task. Nothing here nags, marks
 * an ingredient incomplete, or fills a gap in with a guess.
 *
 * Density is asked per 100 ml rather than per ml because that is the scale
 * people can actually estimate; it is divided by a hundred on save.
 */

// The dimensions each factor makes reachable, in the order they are offered.
const LABELS = { mass: 'Weight', volume: 'Volume', piece: 'Count' }

export default function ConversionFields({ value, onChange, autoFocusField }) {
  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value })
  const reachable = reachableDimensions(toConversions(value))

  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium">How this ingredient converts</legend>
      <p className="text-xs" style={{ color: 'var(--text-subtle)' }}>
        Leave a field blank when that measurement makes no sense for this
        ingredient. Blank is a fine answer, not a missing one.
      </p>

      <div className="space-y-1">
        <label className="text-sm" htmlFor="grams-per-piece">
          One piece weighs
        </label>
        <div className="flex items-center gap-2">
          <Input
            id="grams-per-piece"
            type="number"
            min="0"
            step="any"
            value={value.gramsPerPiece}
            onChange={set('gramsPerPiece')}
            autoFocus={autoFocusField === 'grams_per_piece'}
          />
          <span className="text-sm" style={{ color: 'var(--text-subtle)' }}>
            g
          </span>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm" htmlFor="grams-per-100ml">
          100 ml weighs
        </label>
        <div className="flex items-center gap-2">
          <Input
            id="grams-per-100ml"
            type="number"
            min="0"
            step="any"
            value={value.gramsPer100Ml}
            onChange={set('gramsPer100Ml')}
            autoFocus={autoFocusField === 'grams_per_ml'}
          />
          <span className="text-sm" style={{ color: 'var(--text-subtle)' }}>
            g
          </span>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm" htmlFor="preferred-dimension">
          Usually measured by
        </label>
        <select
          id="preferred-dimension"
          value={value.preferredDimension}
          onChange={set('preferredDimension')}
          className="rounded-xl border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        >
          <option value="">Automatic</option>
          {reachable.map((dimension) => (
            <option key={dimension} value={dimension}>
              {LABELS[dimension]}
            </option>
          ))}
        </select>
      </div>
    </fieldset>
  )
}
