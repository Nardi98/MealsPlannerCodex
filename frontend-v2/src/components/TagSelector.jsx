import React from 'react'
import { CheckIcon, ChevronDownIcon } from '@heroicons/react/24/outline'

export default function TagSelector({ label, tags = [], selected = [], onChange }) {
  const [open, setOpen] = React.useState(false)

  const toggle = (tag) => {
    const exists = selected.includes(tag)
    const next = exists ? selected.filter((t) => t !== tag) : [...selected, tag]
    onChange(next)
  }

  const display = selected.length > 0 ? selected.join(', ') : 'Select tags'

  return (
    <div className="flex flex-col text-sm col-span-2 relative">
      {label && <span className="mb-1">{label}</span>}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="border rounded p-2 flex justify-between items-center"
        style={{ borderColor: 'var(--border)' }}
      >
        <span>{display}</span>
        <ChevronDownIcon className="h-4 w-4" />
      </button>
      {open && (
        <div
          className="absolute z-10 mt-1 w-full bg-white border rounded shadow max-h-60 overflow-y-auto"
          style={{ borderColor: 'var(--border)' }}
        >
          {tags.map((tag) => {
            const isSelected = selected.includes(tag)
            return (
              <div
                key={tag}
                className="flex items-center px-2 py-1 cursor-pointer hover:bg-gray-100"
                onClick={() => toggle(tag)}
              >
                <span className="mr-2 h-4 w-4 flex items-center justify-center">
                  {isSelected && <CheckIcon className="h-4 w-4" />}
                </span>
                <span>{tag}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

