import React from 'react'
import { Card, Button } from './'

export default function MergeConflictModal({ conflicts = [], onCancel, onConfirm }) {
  const [defaultAction, setDefaultAction] = React.useState('keep-old')
  const [selections, setSelections] = React.useState([])

  React.useEffect(() => {
    setSelections(conflicts.map(() => defaultAction))
  }, [defaultAction, conflicts])

  const handleChange = (idx, value) => {
    setSelections((prev) => {
      const copy = [...prev]
      copy[idx] = value
      return copy
    })
  }

  const handleConfirm = () => {
    const result = conflicts.map((c, i) => ({ ...c, action: selections[i] }))
    onConfirm?.(result)
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[70]">
      <Card className="space-y-4 w-full max-w-md" style={{ color: 'var(--text-strong)' }}>
        <h3 className="text-lg font-medium">Resolve Conflicts</h3>
        <div className="space-y-1">
          <label className="text-sm">Default action</label>
          <select
            value={defaultAction}
            onChange={(e) => setDefaultAction(e.target.value)}
            className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
            style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
          >
            <option value="keep-old">Keep old</option>
            <option value="use-new">Use new</option>
            <option value="keep-both">Keep both</option>
          </select>
        </div>
        <div className="max-h-60 overflow-y-auto space-y-4">
          {conflicts.map((c, idx) => (
            <div
              key={`${c.type}-${c.title}-${idx}`}
              className="border-b pb-2 last:border-b-0"
              style={{ borderColor: 'var(--border)' }}
            >
              <div className="text-sm font-medium mb-1">
                {c.type === 'recipe' ? 'Recipe' : 'Ingredient'}: {c.title}
              </div>
              <div className="flex gap-4 text-sm">
                {["keep-old", "use-new", "keep-both"].map((opt) => (
                  <label key={opt} className="flex items-center gap-1">
                    <input
                      type="radio"
                      name={`conflict-${idx}`}
                      value={opt}
                      checked={selections[idx] === opt}
                      onChange={() => handleChange(idx, opt)}
                    />
                    <span className="capitalize">{opt.replace('-', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button onClick={handleConfirm}>Confirm</Button>
        </div>
      </Card>
    </div>
  )
}

