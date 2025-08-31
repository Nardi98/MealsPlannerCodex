import React, { useState } from 'react'
import { Input } from './Input'
import { Button } from './Button'

export default function TagSelector({ tags, selected, onChange, onCreate }) {
  const [newTag, setNewTag] = useState('')

  const toggle = (name) => {
    const exists = selected.includes(name)
    const next = exists ? selected.filter((t) => t !== name) : [...selected, name]
    onChange(next)
  }

  const addTag = () => {
    const name = newTag.trim()
    if (!name) return
    if (!tags.some((t) => t.name === name)) {
      onCreate && onCreate(name)
    }
    onChange([...selected, name])
    setNewTag('')
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {tags.map((t) => (
          <label
            key={t.id || t.name}
            className="flex items-center gap-1 text-sm"
          >
            <input
              type="checkbox"
              className="rounded border"
              style={{ borderColor: 'var(--border)' }}
              checked={selected.includes(t.name)}
              onChange={() => toggle(t.name)}
            />
            {t.name}
          </label>
        ))}
      </div>
      {onCreate && (
        <div className="flex items-center gap-2">
          <Input
            size="sm"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder="New tag"
            className="flex-1"
          />
          <Button type="button" size="sm" variant="a2" onClick={addTag}>
            Add
          </Button>
        </div>
      )}
    </div>
  )
}
