import React from 'react'
import { Button } from './'

export default function ConfirmIngredientChangeModal({ recipes = [], action = 'change', onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[70]">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md space-y-4" style={{ color: 'var(--text-strong)' }}>
        <h3 className="text-lg font-medium">
          {action === 'delete' ? 'Delete Ingredient' : 'Edit Ingredient'}
        </h3>
        {recipes.length ? (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            <p className="text-sm">This ingredient is used in the following recipes:</p>
            <ul className="list-disc pl-5 text-sm">
              {recipes.map((r) => (
                <li key={r.id}>
                  {r.title}
                  <span className="ml-1 text-xs text-[color:var(--text-subtle)]">
                    {(r.ingredients || []).length}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm">This ingredient is not used in any recipes.</p>
        )}
        <p className="text-sm">Are you sure you want to {action} this ingredient?</p>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="a1" onClick={onConfirm}>Confirm</Button>
        </div>
      </div>
    </div>
  )
}
