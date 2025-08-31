import { useState } from 'react'
import RecipeForm from './RecipeForm'

export default function AddRecipeModal({ onRecipeAdded }) {
  const [open, setOpen] = useState(false)

  const handleCreated = (recipe) => {
    onRecipeAdded?.(recipe)
    setOpen(false)
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-2xl px-3 py-2 text-sm shadow-sm hover:opacity-95"
        style={{ backgroundColor: 'var(--c-pos)', color: '#fff' }}
      >
        New recipe
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
          onClick={() => setOpen(false)}
        >
          <div
            className="rounded-2xl border bg-white p-4 shadow-sm"
            style={{ borderColor: 'var(--border)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <RecipeForm onCreated={handleCreated} />
          </div>
        </div>
      )}
    </>
  )
}
