import React from 'react'
import { Button } from './Button'
import SegmentedControl from './SegmentedControl'
import { authApi } from '../api/authApi'
import { ingredientsApi } from '../api/ingredientsApi'

/**
 * Which system this account reads amounts in.
 *
 * Display only, and that is what makes it cheap: the database is always
 * metric, the frontend applies this at render time, so there is no save step,
 * no round trip to wait on, and no way for it to touch a stored quantity.
 *
 * Switching raises exactly one question. US recipes measure by volume where
 * metric ones weigh, so the pantry usually wants to follow -- but that is a
 * *display preference* per ingredient, not a rewrite, which is why it can be
 * one click with an undo. Counted ingredients are never touched, and anything
 * whose conversions cannot reach the target is named plainly rather than
 * nagged about.
 */

const OPTIONS = [
  { value: 'metric', label: 'Metric' },
  { value: 'us', label: 'US' },
]

// Which way of measuring each system leans toward, and the sentence that asks.
const LEANS = {
  us: {
    dimension: 'volume',
    question:
      'US recipes usually measure by volume. Switch your ingredients from weight to volume where possible?',
  },
  metric: {
    dimension: 'mass',
    question:
      'Metric recipes usually measure by weight. Switch your ingredients from volume to weight where possible?',
  },
}

export default function UnitSystemSetting({ value, onChange, switchable = true }) {
  const [asking, setAsking] = React.useState(null)
  const [result, setResult] = React.useState(null)

  const select = async (next) => {
    if (next === value) return
    // Applied first and unconditionally: the rendering change is the setting,
    // and the pantry question is a separate, optional favour.
    await authApi.setUnitSystem(next)
    onChange?.(next)
    if (switchable) setAsking(next)
  }

  const accept = async () => {
    const { dimension } = LEANS[asking]
    setAsking(null)
    setResult(await ingredientsApi.switchPreferredDimension(dimension))
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">Units</label>
      <SegmentedControl options={OPTIONS} value={value} onChange={select} />

      {asking && (
        <div
          className="space-y-2 rounded-xl border p-3 text-sm"
          style={{ borderColor: 'var(--border)' }}
        >
          <p>{LEANS[asking].question}</p>
          <div className="flex gap-2">
            <Button type="button" variant="a1" onClick={accept}>
              Switch
            </Button>
            <Button type="button" variant="ghost" onClick={() => setAsking(null)}>
              Keep as they are
            </Button>
          </div>
        </div>
      )}

      {result && (
        <p className="text-xs" style={{ color: 'var(--text-subtle)' }}>
          {result.switched.length > 0 && (
            <>Switched {result.switched.length}. </>
          )}
          {result.skipped.length > 0 && (
            <>
              Left as they were, with no conversion to switch to:{' '}
              {result.skipped.join(', ')}.
            </>
          )}
        </p>
      )}
    </div>
  )
}
