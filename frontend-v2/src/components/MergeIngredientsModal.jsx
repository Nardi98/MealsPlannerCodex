import React from 'react'
import { Button } from './'
import { ingredientsApi } from '../api/ingredientsApi'
import { ModalScrim } from './Modal'
import { Z } from '../lib/layers'

/**
 * Tool to review candidate duplicate ingredient pairs and merge a chosen pair.
 *
 * Reachable from both the Ingredients page and the Shopping List page. On a
 * successful merge, `onMerged` is called so the parent can refresh its data.
 */
export default function MergeIngredientsModal({ onClose, onMerged }) {
  const [pairs, setPairs] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [selected, setSelected] = React.useState(null)
  const [survivor, setSurvivor] = React.useState('a')
  const [affected, setAffected] = React.useState([])
  const [error, setError] = React.useState(null)

  const loadPairs = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await ingredientsApi.duplicates()
      setPairs(data || [])
    } catch (err) {
      console.error('Failed to load duplicate pairs', err)
      setError('Failed to load duplicate pairs')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadPairs()
  }, [loadPairs])

  const target = selected ? selected[survivor] : null
  const source = selected ? selected[survivor === 'a' ? 'b' : 'a'] : null

  const selectPair = (pair) => {
    // Affected recipes are derived by the effect below.
    setSelected(pair)
    setSurvivor('a')
    setError(null)
  }

  // Keep the affected recipe list in sync when the survivor flips.
  React.useEffect(() => {
    if (!selected) return
    const src = selected[survivor === 'a' ? 'b' : 'a']
    ingredientsApi
      .recipes(src.id)
      .then((recipes) => setAffected(recipes || []))
      .catch((err) => console.error('Failed to load affected recipes', err))
  }, [survivor, selected])

  const handleConfirm = async () => {
    if (!source || !target) return
    try {
      // No bridge to hand over any more: the survivor's own conversions
      // supply it, and lines they cannot reach keep their own dimension.
      await ingredientsApi.merge({
        source_id: source.id,
        target_id: target.id,
      })
      setSelected(null)
      await loadPairs()
      onMerged?.()
    } catch (err) {
      console.error('Failed to merge ingredients', err)
      setError('Failed to merge ingredients')
    }
  }

  return (
    <ModalScrim z={Z.nested}>
      <div
        className="bg-white rounded-2xl p-6 w-full max-w-lg space-y-4"
        style={{ color: 'var(--text-strong)' }}
      >
        <h3 className="text-lg font-medium">Merge ingredients</h3>
        {error && (
          <div className="text-sm" style={{ color: 'var(--c-neg)' }}>
            {error}
          </div>
        )}

        {!selected && (
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {loading ? (
              <p className="text-sm">Loading…</p>
            ) : pairs.length === 0 ? (
              <p className="text-sm">No likely duplicates found.</p>
            ) : (
              pairs.map((pair) => (
                <button
                  key={`${pair.a.id}-${pair.b.id}`}
                  type="button"
                  onClick={() => selectPair(pair)}
                  className="w-full text-left border rounded-xl p-3 text-sm hover:bg-black/5"
                  style={{ borderColor: 'var(--border)' }}
                >
                  <span className="font-medium">
                    {pair.a.name}
                  </span>{' '}
                  ↔{' '}
                  <span className="font-medium">
                    {pair.b.name}
                  </span>
                  <span className="ml-2 text-xs text-[color:var(--text-subtle)]">
                    {Math.round(pair.score * 100)}% · {pair.a.recipe_count}/
                    {pair.b.recipe_count} recipes
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        {selected && (
          <div className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Keep (survivor)</label>
              <div className="flex flex-col gap-1">
                {['a', 'b'].map((key) => (
                  <label key={key} className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="survivor"
                      value={key}
                      checked={survivor === key}
                      onChange={() => setSurvivor(key)}
                    />
                    {selected[key].name}
                  </label>
                ))}
              </div>
            </div>


            <div className="space-y-1">
              <label className="text-sm font-medium">
                Affected recipes ({affected.length})
              </label>
              <ul className="list-disc pl-5 text-sm max-h-32 overflow-y-auto">
                {affected.map((r) => (
                  <li key={r.id}>{r.title}</li>
                ))}
              </ul>
            </div>

            <div className="flex justify-between gap-2 pt-2">
              <Button variant="ghost" onClick={() => setSelected(null)}>
                Back
              </Button>
              <Button variant="a1" onClick={handleConfirm}>
                Merge
              </Button>
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </ModalScrim>
  )
}
