import React from 'react'
import {
  SparklesIcon,
  GlobeAltIcon,
  SunIcon,
  CheckBadgeIcon,
  ArrowPathRoundedSquareIcon,
  AdjustmentsHorizontalIcon,
  Squares2X2Icon,
  Square2StackIcon,
  StopIcon,
} from '@heroicons/react/24/outline'
import { Card } from './Card'
import { Button } from './Button'
import { Input } from './Input'
import DateRangePicker from './DateRangePicker'
import SegmentedControl from './SegmentedControl'
import TagSelector from './TagSelector'
import FridgeSelector from './FridgeSelector'
import SettingTooltip from './SettingTooltip'
import { SETTING_HELP } from './settingHelp'

// Every control is wrapped in its own tooltip, keyed by the help entry it
// explains. The wrapper carries the grid classes so the layout is unchanged.
function Setting({ help, className, children }) {
  const { title, body, presets } = SETTING_HELP[help]
  return (
    <SettingTooltip title={title} body={body} presets={presets} className={className}>
      {children}
    </SettingTooltip>
  )
}

const TABS = [
  { value: 'settings', label: 'Settings' },
  { value: 'fridge', label: 'Your Fridge' },
]

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

const MEALS_OPTIONS = [
  { value: 1, label: '1', sub: 'meal', icon: svg(StopIcon) },
  { value: 2, label: '2', sub: 'meals', icon: svg(Square2StackIcon) },
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
  ingredients,
  message,
  error,
  onChange,
  onRangeChange,
  onPresetChange,
  onAvoidChange,
  onReduceChange,
  onFridgeChange,
  onSubmit,
}) {
  const [activeTab, setActiveTab] = React.useState('settings')
  return (
    <Card data-tour="mealplan-form">
      <form onSubmit={onSubmit} className="space-y-8">
        <div
          role="tablist"
          aria-label="Plan settings sections"
          // The tutorial points here rather than at the whole card: a bubble
          // anchored on something taller than the window has nowhere to sit.
          data-tour="mealplan-tabs"
          className="flex gap-6 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          {TABS.map((tab) => {
            const selected = activeTab === tab.value
            return (
              <button
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setActiveTab(tab.value)}
                className="-mb-px border-b-2 pb-2 text-sm font-bold transition-colors"
                style={{
                  borderColor: selected ? 'var(--c-a2)' : 'transparent',
                  color: selected ? 'var(--c-a2)' : 'var(--text-subtle)',
                }}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
        {activeTab === 'settings' && (
        <div className="space-y-8">
        <div className="grid grid-cols-3 gap-x-6 gap-y-12">
          <Setting help="dates">
            <DateRangePicker
              label="Plan dates"
              start={form.start}
              end={form.end}
              onChange={onRangeChange}
            />
          </Setting>
          <Setting help="meals_per_day">
            <SegmentedControl
              label="Meals per day"
              options={MEALS_OPTIONS}
              value={Number(form.meals_per_day)}
              onChange={(v) => onPresetChange('meals_per_day', v)}
            />
          </Setting>
          <Setting help="epsilon">
            <label className="flex flex-col text-sm">
              <span className="mb-2 font-bold text-base">Recommendation style</span>
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
          </Setting>
        </div>
        <div className="grid grid-cols-4 gap-x-6 gap-y-12">
          <Setting help="leftovers" className="col-span-2">
            <SegmentedControl
              label="Leftovers"
              options={LEFTOVER_OPTIONS}
              value={form.leftovers}
              onChange={(v) => onPresetChange('leftovers', v)}
            />
          </Setting>
          <Setting help="seasonality" className="col-span-2">
            <SegmentedControl
              label="Seasonality"
              options={SEASONALITY_OPTIONS}
              value={form.seasonality}
              onChange={(v) => onPresetChange('seasonality', v)}
            />
          </Setting>
          <Setting help="recency" className="col-span-2">
            <SegmentedControl
              label="Variety"
              options={RECENCY_OPTIONS}
              value={form.recency}
              onChange={(v) => onPresetChange('recency', v)}
            />
          </Setting>
          <Setting help="avoid_tags" className="col-span-1">
            <TagSelector
              label="Avoid tags"
              tags={tags}
              selected={form.avoid_tags}
              onChange={onAvoidChange}
            />
          </Setting>
          <Setting help="reduce_tags" className="col-span-1">
            <TagSelector
              label="Reduce tags"
              tags={tags}
              selected={form.reduce_tags}
              onChange={onReduceChange}
            />
          </Setting>
        </div>
        </div>
        )}
        {activeTab === 'fridge' && (
          <Setting help="fridge">
            <FridgeSelector
              ingredients={ingredients}
              value={form.fridge}
              onChange={onFridgeChange}
            />
          </Setting>
        )}
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
        <Button type="submit" className="mt-2" data-tour="mealplan-generate">Generate plan</Button>
      </form>
    </Card>
  )
}
