import React from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import CategorySelect from '../CategorySelect'
import SeasonalitySelect from '../SeasonalitySelect'
import { mutedTextStyle } from './textStyles'

// The dimensions a system ingredient's quantities may be measured in, spelled
// as the enum stores them. '' is "not recorded", which the server takes as null.
const DIMENSIONS = [
  { value: '', label: 'Not recorded' },
  { value: 'mass', label: 'Mass (g)' },
  { value: 'volume', label: 'Volume (ml)' },
  { value: 'piece', label: 'Pieces' },
]

// A number field's text → what the server stores: a blank clears the value.
const asNumber = (text) => (String(text).trim() === '' ? null : Number(text))

// ...and back, so an unset field renders empty rather than as "null".
const asText = (value) => (value === null || value === undefined ? '' : String(value))

const sameList = (a, b) => a.length === b.length && a.every((item, i) => item === b[i])

const fieldsOf = (ingredient) => ({
  name: ingredient?.name ?? '',
  season_months: ingredient?.season_months ?? [],
  categories: ingredient?.categories ?? [],
  grams_per_ml: asText(ingredient?.grams_per_ml),
  grams_per_piece: asText(ingredient?.grams_per_piece),
  preferred_dimension: ingredient?.preferred_dimension ?? '',
})

/**
 * The create/edit form for one **system** ingredient — the vocabulary page's
 * form and, unchanged, the one the import review page raises to name an
 * ingredient the file mentions but the catalog does not own yet.
 *
 * It is a plain controlled form, not a modal, precisely so both can use it:
 * the page decides where it sits and what surrounds it.
 *
 * Props:
 *  - `ingredient`: the row being edited, or null/absent to create one.
 *  - `heading`: optional caption above the fields.
 *  - `submitLabel`: the submit button's words (also its accessible name).
 *  - `busy`: disables submit while the caller's write is in flight.
 *  - `error`: the caller's failure, shown as an alert above the buttons.
 *  - `onSubmit(changes)`: **the whole ingredient when creating**, and only the
 *    fields that actually changed when editing. That asymmetry is the point:
 *    `PUT` is partial, so an omitted key leaves the stored value alone while an
 *    explicit `null` clears it, and sending every field would make "leave it"
 *    impossible to express.
 *  - `onCancel`: omitted when there is nowhere to go back to, and then no
 *    Cancel button is rendered.
 *
 * The fields are seeded from `ingredient` once, so **callers must key this
 * component by the row's identity** (both do) to switch it to another row.
 * That is the whole reset mechanism: an effect watching the row as well would
 * be a second one that can only disagree with the first.
 */
export default function SystemIngredientForm({
  ingredient = null,
  heading = null,
  submitLabel = 'Save',
  busy = false,
  error = null,
  onSubmit,
  onCancel = null,
}) {
  const id = React.useId()
  const [fields, setFields] = React.useState(() => fieldsOf(ingredient))
  const [problem, setProblem] = React.useState(null)

  const set = (key) => (value) => setFields((current) => ({ ...current, [key]: value }))
  const onText = (key) => (event) => set(key)(event.target.value)

  const submit = (event) => {
    event.preventDefault()
    const name = fields.name.trim()
    if (!name) {
      setProblem('An ingredient needs a name.')
      return
    }
    const next = {
      name,
      season_months: fields.season_months,
      categories: fields.categories,
      grams_per_ml: asNumber(fields.grams_per_ml),
      grams_per_piece: asNumber(fields.grams_per_piece),
      preferred_dimension: fields.preferred_dimension || null,
    }
    setProblem(null)
    if (!ingredient) {
      onSubmit(next)
      return
    }
    const before = {
      ...fieldsOf(ingredient),
      grams_per_ml: ingredient.grams_per_ml ?? null,
      grams_per_piece: ingredient.grams_per_piece ?? null,
      preferred_dimension: ingredient.preferred_dimension ?? null,
    }
    const changes = {}
    for (const [key, value] of Object.entries(next)) {
      const unchanged = Array.isArray(value) ? sameList(value, before[key]) : value === before[key]
      if (!unchanged) changes[key] = value
    }
    onSubmit(changes)
  }

  const shown = problem || error

  return (
    <form className="flex flex-col gap-3" onSubmit={submit}>
      {heading && (
        <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>{heading}</h3>
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-name`} style={mutedTextStyle}>
          Name
        </label>
        <Input id={`${id}-name`} value={fields.name} onChange={onText('name')} autoComplete="off" />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="flex flex-col gap-1">
          <span style={mutedTextStyle}>In season</span>
          <SeasonalitySelect value={fields.season_months} onChange={set('season_months')} />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-dimension`} style={mutedTextStyle}>
            Measured in
          </label>
          <Input as="select" id={`${id}-dimension`} value={fields.preferred_dimension} onChange={onText('preferred_dimension')}>
            {DIMENSIONS.map((dimension) => (
              <option key={dimension.value} value={dimension.value}>
                {dimension.label}
              </option>
            ))}
          </Input>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-gpml`} style={mutedTextStyle}>
            Grams per ml
          </label>
          <Input
            id={`${id}-gpml`}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            value={fields.grams_per_ml}
            onChange={onText('grams_per_ml')}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-gpp`} style={mutedTextStyle}>
            Grams per piece
          </label>
          <Input
            id={`${id}-gpp`}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            value={fields.grams_per_piece}
            onChange={onText('grams_per_piece')}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <span style={mutedTextStyle}>Categories</span>
        <CategorySelect value={fields.categories} onChange={set('categories')} />
      </div>

      {shown && (
        <p role="alert" style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-neg)' }}>
          {shown}
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" disabled={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
