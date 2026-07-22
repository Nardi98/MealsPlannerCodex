import React from 'react'
import {
  SparklesIcon,
  GlobeAltIcon,
  SunIcon,
  CheckBadgeIcon,
  ArrowPathRoundedSquareIcon,
  AdjustmentsHorizontalIcon,
  Squares2X2Icon,
} from '@heroicons/react/24/outline'
import { Card } from './Card'
import { Button } from './Button'
import { Input } from './Input'
import DateRangePicker from './DateRangePicker'
import SegmentedControl from './SegmentedControl'
import TagSelector from './TagSelector'

// eslint-disable-next-line no-unused-vars -- `Icon` is rendered as a JSX component
const svg = (Icon) => <Icon className="seg-svg" aria-hidden="true" />
const png = (src, alt) => (
  <img className="segu-ico" src={src} alt={alt} aria-hidden="true" />
)

const LEFTOVER_OPTIONS = [
  { value: 'fresh', label: 'Everything', sub: 'fresh', icon: svg(SparklesIcon) },
  {
    value: 'some',
    label: 'Some',
    sub: 'leftovers',
    icon: png('/assets/icons/left_overs_icon.png', 'leftovers'),
  },
  {
    value: 'lots',
    label: 'Cook',
    sub: 'in bulk',
    icon: png('/assets/icons/bulk_icon.png', 'cook in bulk'),
  },
]

const SEASONALITY_OPTIONS = [
  { value: 'ignore', label: "Don't care", sub: 'about seasons', icon: svg(GlobeAltIcon) },
  { value: 'prefer', label: 'Prefer', sub: 'seasonal', icon: svg(SunIcon) },
  { value: 'strict', label: 'Strictly', sub: 'seasonal', icon: svg(CheckBadgeIcon) },
]

const RECENCY_OPTIONS = [
  { value: 'low', label: 'Repeat', sub: 'freely', icon: svg(ArrowPathRoundedSquareIcon) },
  { value: 'medium', label: 'Some', sub: 'variety', icon: svg(AdjustmentsHorizontalIcon) },
  { value: 'high', label: 'Maximise', sub: 'variety', icon: svg(Squares2X2Icon) },
]

/**
 * The plan-generation form. Weights are chosen through preset segmented rows
 * (leftovers, seasonality, variety) rather than raw numbers; the ε slider is
 * reframed as a Favorite food ↔ Random selection dial. Presentational — state
 * and handlers come from the `useGeneration` hook via props.
 */
export default function GenerationForm({
  form,
  tags,
  message,
  error,
  onChange,
  onRangeChange,
  onPresetChange,
  onAvoidChange,
  onReduceChange,
  onSubmit,
}) {
  return (
    <Card>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <DateRangePicker
            label="Plan dates"
            start={form.start}
            end={form.end}
            onChange={onRangeChange}
          />
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
          <div className="col-span-2">
            <SegmentedControl
              label="Leftovers"
              options={LEFTOVER_OPTIONS}
              value={form.leftovers}
              onChange={(v) => onPresetChange('leftovers', v)}
            />
          </div>
          <div className="col-span-2">
            <SegmentedControl
              label="Seasonality"
              options={SEASONALITY_OPTIONS}
              value={form.seasonality}
              onChange={(v) => onPresetChange('seasonality', v)}
            />
          </div>
          <div className="col-span-2">
            <SegmentedControl
              label="Variety"
              options={RECENCY_OPTIONS}
              value={form.recency}
              onChange={(v) => onPresetChange('recency', v)}
            />
          </div>
          <label className="flex flex-col text-sm col-span-2">
            <span className="mb-1">Recommendation style</span>
            <Input
              type="range"
              name="epsilon"
              min="0"
              max="1"
              step="0.01"
              value={form.epsilon}
              onChange={onChange}
            />
            <div
              className="flex justify-between text-xs mt-1"
              style={{ color: 'var(--text-subtle)' }}
            >
              <span>Favorite food</span>
              <span>Random selection</span>
            </div>
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
