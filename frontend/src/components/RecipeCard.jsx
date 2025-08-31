import React, { useState } from 'react'

function Card({ children, onClick }) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-2xl border bg-white p-4 shadow-sm"
      style={{ borderColor: 'var(--border)' }}
    >
      {children}
    </div>
  )
}

function Badge({ tone = 'a3', children }) {
  const fg = `var(--c-${tone})`
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
      style={{
        backgroundColor: `color-mix(in srgb, ${fg} 14%, transparent)`,
        color: fg,
      }}
    >
      {children}
    </span>
  )
}

function Button({ variant = 'primary', children, onClick }) {
  const map = {
    primary: { bg: 'var(--c-pos)', fg: '#fff' },
    danger: { bg: 'var(--c-neg)', fg: '#fff' },
    a1: { bg: 'var(--c-a1)', fg: '#fff' },
    a2: { bg: 'var(--c-a2)', fg: '#fff' },
    ghost: { bg: 'transparent', fg: 'var(--text-strong)' },
  }[variant] || { bg: 'var(--c-pos)', fg: '#fff' }
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-2xl px-3 py-2 text-sm shadow-sm hover:opacity-95"
      style={{ backgroundColor: map.bg, color: map.fg }}
      type="button"
    >
      {children}
    </button>
  )
}

export default function RecipeCard({ recipe, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const toggle = () => setExpanded((e) => !e)

  const handleEdit = (e) => {
    e.stopPropagation()
    onEdit && onEdit(recipe)
  }

  const handleDelete = (e) => {
    e.stopPropagation()
    onDelete && onDelete(recipe.id)
  }

  const ingredients = recipe.ingredients || []
  const tags = recipe.tags || []

  return (
    <Card onClick={toggle}>
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[var(--text-strong)]">{recipe.title}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {recipe.course && <Badge tone="a3">{recipe.course}</Badge>}
          {tags.map((tag) => (
            <Badge key={tag}>{tag}</Badge>
          ))}
        </div>
        {expanded && (
          <div className="mt-2 space-y-2 text-sm text-[var(--text-strong)]">
            {ingredients.length > 0 && (
              <ul className="list-disc pl-5">
                {ingredients.map((ing, i) => (
                  <li key={i}>
                    {[ing.quantity, ing.unit, ing.name].filter(Boolean).join(' ')}
                  </li>
                ))}
              </ul>
            )}
            {recipe.procedure && (
              <p className="whitespace-pre-wrap text-[var(--text-muted)]">
                {recipe.procedure}
              </p>
            )}
            {(onEdit || onDelete) && (
              <div className="flex gap-2">
                {onEdit && <Button variant="a1" onClick={handleEdit}>Edit</Button>}
                {onDelete && <Button variant="danger" onClick={handleDelete}>Delete</Button>}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
