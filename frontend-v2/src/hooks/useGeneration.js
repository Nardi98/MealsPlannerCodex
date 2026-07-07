import React from 'react'
import { mealPlansApi } from '../api/mealPlansApi'
import { startOfWeek, fmt } from './useMealPlan'

const defaultForm = () => {
  const start = startOfWeek(new Date())
  const end = startOfWeek(new Date())
  end.setDate(end.getDate() + 6)
  return {
    start: fmt(start),
    end: fmt(end),
    meals_per_day: 2,
    epsilon: 0.25,
    seasonality_weight: 1,
    recency_weight: 1,
    tag_penalty_weight: 1,
    bulk_bonus_weight: 1,
    keep_days: 3,
    bulk_leftovers: true,
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
    const { name, value, type, checked } = e.target
    let val = type === 'checkbox' ? checked : value
    if (name === 'meals_per_day') {
      const num = Number(value)
      val = isNaN(num) ? 1 : Math.max(1, num)
    }
    setForm((f) => ({ ...f, [name]: val }))
  }

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
              side_ids: [],
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
      const params = {
        start: form.start,
        end: form.end,
        meals_per_day: Number(form.meals_per_day) || 1,
        epsilon: Number(form.epsilon),
        seasonality_weight: Number(form.seasonality_weight),
        recency_weight: Number(form.recency_weight),
        tag_penalty_weight: Number(form.tag_penalty_weight),
        bulk_bonus_weight: Number(form.bulk_bonus_weight),
        bulk_leftovers: Boolean(form.bulk_leftovers),
        avoid_tags: form.avoid_tags,
        reduce_tags: form.reduce_tags,
        keep_days: Number(form.keep_days),
      }
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
