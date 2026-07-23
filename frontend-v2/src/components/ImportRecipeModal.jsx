import React from 'react'
import { Input, Button } from './'
import SeasonalitySelect from './SeasonalitySelect'
import CategorySelect from './CategorySelect'
import NewRecipeModal from './NewRecipeModal'
import ExistingIngredientPicker from './ExistingIngredientPicker'
import {
  IMPORT_PROMPT,
  IMPORT_SUGGESTION_THRESHOLD,
  UNITS,
  parseImportedRecipe,
} from '../constants/recipeImport'
import { ingredientsApi } from '../api/ingredientsApi'
import { recipesApi } from '../api/recipesApi'

// Build one reconciliation row per imported ingredient. An exact name match
// (case-insensitive) against an existing ingredient defaults the row to reusing
// it; otherwise the row defaults to creating a new ingredient.
function buildRows(ingredients, existing, suggestionsByIndex) {
  const byName = new Map(existing.map((e) => [e.name.toLowerCase(), e]))
  return ingredients.map((ing, i) => {
    const match = byName.get(ing.name.toLowerCase())
    const suggestions = suggestionsByIndex[i] || []
    return {
      amount: ing.amount,
      mode: match ? 'existing' : 'new',
      matched: Boolean(match),
      existingId: match ? match.id : suggestions[0]?.id,
      name: ing.name,
      unit: ing.unit || '',
      season: ing.season_months || [],
      categories: [],
      suggestions,
    }
  })
}

function ErrorList({ errors }) {
  if (!errors.length) return null
  return (
    <ul className="text-sm space-y-1" style={{ color: 'var(--c-neg)' }}>
      {errors.map((e) => (
        <li key={e}>{e}</li>
      ))}
    </ul>
  )
}

function UnitSelect({ label, value, onChange }) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required
      className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
      style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
    >
      <option value="">Select unit</option>
      {UNITS.map((u) => (
        <option key={u} value={u}>{u}</option>
      ))}
    </select>
  )
}

export default function ImportRecipeModal({ onClose, onCreated }) {
  const [step, setStep] = React.useState('prompt')
  const [raw, setRaw] = React.useState('')
  const [errors, setErrors] = React.useState([])
  const [copied, setCopied] = React.useState(false)
  const [recipe, setRecipe] = React.useState(null)
  const [rows, setRows] = React.useState([])
  const [existing, setExisting] = React.useState([])
  const [busy, setBusy] = React.useState(false)

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(IMPORT_PROMPT)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  const handleContinue = async () => {
    const { recipe: parsed, errors: errs } = parseImportedRecipe(raw)
    if (errs.length) {
      setErrors(errs)
      return
    }
    setErrors([])
    setRecipe(parsed)
    try {
      const [ings, ...suggestions] = await Promise.all([
        ingredientsApi.fetchAll(),
        ...parsed.ingredients.map((ing) =>
          ingredientsApi
            .similar(ing.name, undefined, IMPORT_SUGGESTION_THRESHOLD)
            .catch(() => [])
        ),
      ])
      setExisting(ings)
      setRows(buildRows(parsed.ingredients, ings, suggestions))
    } catch (err) {
      console.error('Failed to load ingredients', err)
      setExisting([])
      setRows(buildRows(parsed.ingredients, [], []))
    }
    setStep('reconcile')
  }

  const updateRow = (idx, patch) =>
    setRows((rs) => rs.map((r, i) => (i === idx ? { ...r, ...patch } : r)))

  const confirmIngredients = async () => {
    setBusy(true)
    try {
      const resolved = []
      for (const row of rows) {
        if (row.mode === 'existing') {
          const ing = existing.find((e) => e.id === row.existingId)
          resolved.push({
            id: ing?.id,
            name: ing?.name ?? row.name,
            amount: row.amount,
            unit: ing?.unit ?? row.unit,
          })
        } else {
          const created = await ingredientsApi.create({
            name: row.name,
            unit: row.unit,
            season: row.season,
            categories: row.categories,
          })
          resolved.push({
            id: created.id,
            name: created.name,
            amount: row.amount,
            unit: created.unit ?? row.unit,
          })
        }
      }
      setRecipe((r) => ({ ...r, ingredients: resolved }))
      setStep('editor')
    } catch (err) {
      console.error('Failed to reconcile ingredients', err)
      setErrors(['Failed to create an ingredient. Please try again.'])
    } finally {
      setBusy(false)
    }
  }

  const handleSave = async (edited) => {
    try {
      const created = await recipesApi.create(edited)
      onCreated?.(created)
    } catch (err) {
      console.error('Failed to create recipe', err)
    }
  }

  if (step === 'editor') {
    return (
      <NewRecipeModal
        initialRecipe={recipe}
        onClose={onClose}
        onSave={handleSave}
      />
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div
        className="bg-white rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto"
        style={{ color: 'var(--text-strong)' }}
      >
        {step === 'prompt' && (
          <div className="space-y-4">
            <h2 className="text-lg font-medium">Import a recipe from the web</h2>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Copy this prompt into any chatbot together with the recipe&apos;s URL or
              text, then paste back the JSON it returns.
            </p>
            <textarea
              readOnly
              value={IMPORT_PROMPT}
              rows={8}
              className="w-full rounded-xl border px-3 py-2 text-xs font-mono"
              style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
            />
            <Button type="button" variant="ghost" size="sm" onClick={copyPrompt}>
              {copied ? 'Copied!' : 'Copy prompt'}
            </Button>
            <div className="space-y-1">
              <label className="text-sm" htmlFor="import-json">
                Paste the JSON the chatbot returned
              </label>
              <textarea
                id="import-json"
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                rows={5}
                className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
                style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
              />
            </div>
            <ErrorList errors={errors} />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button variant="a1" onClick={handleContinue} disabled={!raw.trim()}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {step === 'reconcile' && (
          <div className="space-y-4">
            <h2 className="text-lg font-medium">Match ingredients</h2>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Reuse an existing ingredient or create a new one for each item.
            </p>
            <div className="space-y-4">
              {rows.map((row, idx) => (
                <div
                  key={idx}
                  className="border-b pb-3 last:border-b-0 space-y-2"
                  style={{ borderColor: 'var(--border)' }}
                >
                  <div className="text-sm font-medium">
                    {row.amount} {row.unit} {row.name}
                  </div>
                  <div className="flex gap-4 text-sm">
                    <label className="flex items-center gap-1">
                      <input
                        type="radio"
                        name={`mode-${idx}`}
                        checked={row.mode === 'existing'}
                        onChange={() => updateRow(idx, { mode: 'existing' })}
                      />
                      Use existing
                    </label>
                    <label className="flex items-center gap-1">
                      <input
                        type="radio"
                        name={`mode-${idx}`}
                        checked={row.mode === 'new'}
                        onChange={() => updateRow(idx, { mode: 'new' })}
                      />
                      Create new
                    </label>
                  </div>

                  {row.mode === 'existing' ? (
                    <div className="space-y-1">
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {row.matched
                          ? `Matches existing: ${row.name}`
                          : 'Link to an existing ingredient'}
                      </div>
                      <ExistingIngredientPicker
                        value={row.existingId}
                        options={existing}
                        suggestions={row.suggestions}
                        onChange={(id) => updateRow(idx, { existingId: id })}
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex gap-2">
                        <Input
                          aria-label={`${row.name} name`}
                          value={row.name}
                          onChange={(e) => updateRow(idx, { name: e.target.value })}
                        />
                        <UnitSelect
                          label={`${row.name} unit`}
                          value={row.unit}
                          onChange={(v) => updateRow(idx, { unit: v })}
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          Seasonality
                        </label>
                        <SeasonalitySelect
                          value={row.season}
                          onChange={(v) => updateRow(idx, { season: v })}
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          Categories
                        </label>
                        <CategorySelect
                          value={row.categories}
                          onChange={(v) => updateRow(idx, { categories: v })}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <ErrorList errors={errors} />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setStep('prompt')}>Back</Button>
              <Button variant="a1" onClick={confirmIngredients} disabled={busy}>
                Confirm ingredients
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
