import React from 'react'
import { Modal } from './Modal'
import { useOptionalAuth } from '../auth/AuthContext'
import { Button } from './Button'
import SegmentedControl from './SegmentedControl'
import { planSettingsApi } from '../api/planSettingsApi'
import { ingredientsApi } from '../api/ingredientsApi'
import UnitSystemSetting from './UnitSystemSetting'
import { reachableDimensions } from '../utils/units'

// Tag-penalty preset -> weight. This is a per-user profile setting (how hard
// "reduce tags" are pushed down), kept out of the per-plan form.
const TAG_PENALTY_PRESETS = { off: 0, reduce: 1, strong: 2 }
const TAG_PENALTY_OPTIONS = [
  { value: 'off', label: 'Off' },
  { value: 'reduce', label: 'Reduce' },
  { value: 'strong', label: 'Strongly reduce' },
]

const presetFromWeight = (weight) => {
  const match = Object.entries(TAG_PENALTY_PRESETS).find(([, w]) => w === weight)
  return match ? match[0] : 'reduce'
}

/**
 * Profile preferences dialog. Loads the caller's plan settings and lets them
 * pick how strongly "reduce tags" are penalised, persisting it as a weight.
 */
export default function PreferencesModal({ onClose }) {
  const [tagPenalty, setTagPenalty] = React.useState('reduce')
  const auth = useOptionalAuth()
  // The popup is only worth raising when some ingredient could actually move,
  // so an account whose pantry cannot switch is never asked.
  const [switchable, setSwitchable] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    let active = true
    ingredientsApi
      .fetchAll()
      .then((ings) => {
        if (!active) return
        setSwitchable(
          (ings || []).some((i) => reachableDimensions(i).length > 1),
        )
      })
      .catch(() => active && setSwitchable(false))
    return () => {
      active = false
    }
  }, [])

  React.useEffect(() => {
    let active = true
    planSettingsApi
      .get()
      .then((settings) => {
        if (active) setTagPenalty(presetFromWeight(settings?.tag_penalty_weight))
      })
      .catch((err) => active && setError(err.message))
    return () => {
      active = false
    }
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await planSettingsApi.update({
        tag_penalty_weight: TAG_PENALTY_PRESETS[tagPenalty],
      })
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Preferences" onClose={onClose}>
      <div className="space-y-4">
        <UnitSystemSetting
          value={auth?.user?.unit_system || 'metric'}
          switchable={switchable}
          onChange={() => auth?.refreshUser?.()}
        />
        <SegmentedControl
          label="Reduced tags"
          options={TAG_PENALTY_OPTIONS}
          value={tagPenalty}
          onChange={setTagPenalty}
        />
        {error && (
          <div className="text-sm" style={{ color: 'var(--c-neg)' }}>
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            Save
          </Button>
        </div>
      </div>
    </Modal>
  )
}
