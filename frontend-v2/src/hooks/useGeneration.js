import React from 'react'
import { mealPlansApi } from '../api/mealPlansApi'
import { startOfWeek, fmt } from './useMealPlan'

// Leftover preset -> the backend leftover/bulk knobs it stands for. Fresh means
// "cook every meal" (no leftovers); Lots leans hard on batch-cooked reuse.
export const LEFTOVER_PRESETS = {
  fresh: { bulk_leftovers: false, bulk_bonus_weight: 0, keep_days: 0 },
  some: { bulk_leftovers: true, bulk_bonus_weight: 1, keep_days: 3 },
  lots: { bulk_leftovers: true, bulk_bonus_weight: 2, keep_days: 5 },
}

// Seasonality preset -> seasonality_weight (0 ignores seasons, higher favours them).
export const SEASONALITY_PRESETS = { ignore: 0, prefer: 1, strict: 3 }

// Recency preset -> recency_weight (how strongly recently-eaten recipes are avoided).
export const RECENCY_PRESETS = { low: 0.5, medium: 1, high: 2 }

/**
 * Map the preset-based form state to the flat weight payload the generate
 * endpoint expects. `tag_penalty_weight` is intentionally omitted: it is now a
 * per-user profile setting sourced by the backend, not a per-plan knob.
 */
export const buildGenerateParams = (form) => {
  const leftover = LEFTOVER_PRESETS[form.leftovers] ?? LEFTOVER_PRESETS.some
  return {
    start: form.start,
    end: form.end,
    meals_per_day: Number(form.meals_per_day) || 1,
    epsilon: Number(form.epsilon),
    seasonality_weight: SEASONALITY_PRESETS[form.seasonality] ?? SEASONALITY_PRESETS.prefer,
    recency_weight: RECENCY_PRESETS[form.recency] ?? RECENCY_PRESETS.medium,
    bulk_bonus_weight: leftover.bulk_bonus_weight,
    bulk_leftovers: leftover.bulk_leftovers,
    keep_days: leftover.keep_days,
    avoid_tags: form.avoid_tags,
    reduce_tags: form.reduce_tags,
  }
}

const defaultForm = () => {
  const start = startOfWeek(new Date())
  const end = startOfWeek(new Date())
  end.setDate(end.getDate() + 6)
  return {
    start: fmt(start),
    end: fmt(end),
    meals_per_day: 2,
    epsilon: 0.25,
    leftovers: 'some',
    seasonality: 'prefer',
    recency: 'medium',
    avoid_tags: [],
    reduce_tags: [],
  }
}

/**
 * Owns the plan-generation flow: the generation form, the generate request,
 * and the overwrite-conflict confirmation handshake. `setPlan` is the plan
 * setter from `useMealPlan`, which this hook updates on a successful generation.
 */
export function useGeneration({ setPlan }) {
  const [form, setForm] = React.useState(defaultForm)
  const [message, setMessage] = React.useState('')
  const [error, setError] = React.useState('')
  const [showOverwriteModal, setShowOverwriteModal] = React.useState(false)
  const [conflictDays, setConflictDays] = React.useState([])
  const [pendingGeneration, setPendingGeneration] = React.useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    let val = value
    if (name === 'meals_per_day') {
      const num = Number(value)
      val = isNaN(num) ? 1 : Math.max(1, num)
    }
    setForm((f) => ({ ...f, [name]: val }))
  }

  const handlePresetChange = (name, value) =>
    setForm((f) => ({ ...f, [name]: value }))

  const handleRangeChange = ({ start, end }) =>
    setForm((f) => ({ ...f, start, end }))

  const handleAvoidChange = (selected) =>
    setForm((f) => ({ ...f, avoid_tags: selected }))
  const handleReduceChange = (selected) =>
    setForm((f) => ({ ...f, reduce_tags: selected }))

  const executeGeneration = async (config) => {
    if (!config) return false
    const { params, range } = config
    try {
      const generated = await mealPlansApi.generate(params)
      const payload = {
        plan_date: range.start,
        plan: Object.fromEntries(
          Object.entries(generated || {}).map(([day, meals]) => [
            day,
            meals.map((m) => ({
              main_id: m.id,
              side_ids: m.side_ids || [],
              leftover: m.leftover,
            })),
          ]),
        ),
        bulk_leftovers: Boolean(params.bulk_leftovers),
        keep_days: Number(params.keep_days),
      }
      try {
        await mealPlansApi.create(payload)
      } catch (err) {
        if (err.data?.conflicts?.length) {
          const conflictList = [...err.data.conflicts].sort()
          setConflictDays(conflictList)
          setPendingGeneration(config)
          setShowOverwriteModal(true)
          return false
        }
        throw err
      }
      const updated = await mealPlansApi.fetchRange(range.start, range.end)
      const resetAccepted = Object.fromEntries(
        Object.entries(updated || {}).map(([day, meals]) => [
          day,
          meals.map((m) => ({ ...m, accepted: false })),
        ])
      )
      setPlan((prev) => ({ ...prev, ...resetAccepted }))
      setMessage('Plan generated successfully.')
      setPendingGeneration(null)
      return true
    } catch (err) {
      setError(err.message)
      setPendingGeneration(null)
      return false
    }
  }

  const handleGenerate = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const days = (new Date(form.end) - new Date(form.start)) / 86400000 + 1
      if (days < 1) {
        setError('End date cannot be before start date')
        return
      }
      const params = buildGenerateParams(form)
      const range = { start: form.start, end: form.end }
      const config = { params, range }
      setPendingGeneration(config)
      const existing = await mealPlansApi.fetchRange(range.start, range.end)
      const conflicts = Object.entries(existing || {})
        .filter(([, meals]) => Array.isArray(meals) && meals.length > 0)
        .map(([day]) => day)
      if (conflicts.length) {
        setConflictDays(conflicts.sort())
        setShowOverwriteModal(true)
        return
      }
      await executeGeneration(config)
    } catch (err) {
      setPendingGeneration(null)
      setError(err.message)
    }
  }

  const handleCancelOverwrite = () => {
    setShowOverwriteModal(false)
    setConflictDays([])
    setPendingGeneration(null)
  }

  const handleConfirmOverwrite = async () => {
    if (!pendingGeneration) {
      setShowOverwriteModal(false)
      return
    }
    setError('')
    setMessage('')
    const { range } = pendingGeneration
    try {
      await mealPlansApi.deleteRange(range.start, range.end)
      if (conflictDays.length) {
        setPlan((prev) => {
          const next = { ...prev }
          let changed = false
          conflictDays.forEach((day) => {
            if (Object.prototype.hasOwnProperty.call(next, day)) {
              delete next[day]
              changed = true
            }
          })
          return changed ? next : prev
        })
      }
      setShowOverwriteModal(false)
      setConflictDays([])
      await executeGeneration(pendingGeneration)
    } catch (err) {
      setShowOverwriteModal(false)
      setError(err.message)
    }
  }

  return {
    form,
    setForm,
    handleChange,
    handlePresetChange,
    handleRangeChange,
    handleAvoidChange,
    handleReduceChange,
    handleGenerate,
    message,
    error,
    setError,
    setMessage,
    showOverwriteModal,
    conflictDays,
    handleCancelOverwrite,
    handleConfirmOverwrite,
  }
}
