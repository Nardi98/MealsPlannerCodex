import React from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { Input } from './Input'
import TagSelector from './TagSelector'

/**
 * The plan-generation form (dates, weights, ε, leftovers, tag filters) plus its
 * success/error messages. Presentational — form state and handlers come from
 * the `useGeneration` hook via props.
 */
export default function GenerationForm({
  form,
  tags,
  message,
  error,
  onChange,
  onAvoidChange,
  onReduceChange,
  onSubmit,
}) {
  return (
    <Card>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col text-sm">
            <span className="mb-1">Start date</span>
            <Input type="date" name="start" value={form.start} onChange={onChange} />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">End date</span>
            <Input type="date" name="end" value={form.end} onChange={onChange} />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">Meals per day</span>
            <Input
              type="number"
              name="meals_per_day"
              min="1"
              max="2"
              step="1"
              value={form.meals_per_day}
              onChange={onChange}
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">ε ({form.epsilon})</span>
            <Input
              type="range"
              name="epsilon"
              min="0"
              max="1"
              step="0.01"
              value={form.epsilon}
              onChange={onChange}
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">Seasonality weight</span>
            <Input type="number" step="0.1" name="seasonality_weight" value={form.seasonality_weight} onChange={onChange} />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">Recency weight</span>
            <Input type="number" step="0.1" name="recency_weight" value={form.recency_weight} onChange={onChange} />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">Tag penalty weight</span>
            <Input type="number" step="0.1" name="tag_penalty_weight" value={form.tag_penalty_weight} onChange={onChange} />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">Bulk bonus weight</span>
            <Input type="number" step="0.1" name="bulk_bonus_weight" value={form.bulk_bonus_weight} onChange={onChange} />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">Keep days</span>
            <Input type="number" name="keep_days" min="0" value={form.keep_days} onChange={onChange} />
          </label>
          <label className="flex items-center gap-2 col-span-2 text-sm">
            <input
              type="checkbox"
              name="bulk_leftovers"
              checked={form.bulk_leftovers}
              onChange={onChange}
              className="h-4 w-4 rounded border"
              style={{ borderColor: 'var(--border)' }}
            />
            <span style={{ color: 'var(--text-strong)' }}>Bulk leftovers</span>
          </label>
          <TagSelector
            label="Avoid tags"
            tags={tags}
            selected={form.avoid_tags}
            onChange={onAvoidChange}
          />
          <TagSelector
            label="Reduce tags"
            tags={tags}
            selected={form.reduce_tags}
            onChange={onReduceChange}
          />
        </div>
        {message && (
          <div className="text-sm" style={{ color: 'var(--c-pos)' }}>
            {message}
          </div>
        )}
        {error && (
          <div className="text-sm" style={{ color: 'var(--c-neg)' }}>
            {error}
          </div>
        )}
        <Button type="submit">Generate plan</Button>
      </form>
    </Card>
  )
}
