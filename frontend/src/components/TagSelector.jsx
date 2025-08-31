import React, { useState } from 'react'
import { Badge, Button, Input } from '../ui'

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
      <div className="flex flex-wrap gap-2">
        {tags.map((t) => (
          <label key={t.id || t.name} className="cursor-pointer">
            <input
              type="checkbox"
              checked={selected.includes(t.name)}
              onChange={() => toggle(t.name)}
              className="sr-only"
            />
            <Badge className={selected.includes(t.name) ? '' : 'opacity-50'}>{t.name}</Badge>
          </label>
        ))}
      </div>
      {onCreate && (
        <div className="mt-2 flex items-center gap-2">
          <Input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder="New tag"
          />
          <Button type="button" variant="a1" onClick={addTag}>
            Add
          </Button>
        </div>
      )}
    </div>
  )
}
