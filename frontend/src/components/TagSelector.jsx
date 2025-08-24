import React, { useState } from 'react'

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
    <div>
      <div>
        {tags.map((t) => (
          <label key={t.id || t.name} style={{ marginRight: '0.5rem' }}>
            <input
              type="checkbox"
              checked={selected.includes(t.name)}
              onChange={() => toggle(t.name)}
            />
            {t.name}
          </label>
        ))}
      </div>
      {onCreate && (
        <div>
          <input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder="New tag"
          />
          <button type="button" onClick={addTag}>
            Add
          </button>
        </div>
      )}
    </div>
  )
}
