import React from 'react'
import { BookmarkIcon, TagIcon } from '@heroicons/react/24/outline'
import { motion as Motion } from 'framer-motion'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { NewRecipeModal } from '../components'
import { recipesApi } from '../api/recipesApi'

export default function RecipesPage() {
  const [recipes, setRecipes] = React.useState([])
  const [expanded, setExpanded] = React.useState(null)
  const [showModal, setShowModal] = React.useState(false)
  const [editing, setEditing] = React.useState(null)

  React.useEffect(() => {
    async function load() {
      try {
        const data = await recipesApi.fetchAll()
        setRecipes(data)
      } catch (err) {
        console.error('Failed to load recipes', err)
      }
    }
    load()
  }, [])

  const toggle = (id) => setExpanded(expanded === id ? null : id)

  const handleSave = async (recipe) => {
    try {
      if (editing) {
        const updated = await recipesApi.update(editing.id, recipe)
        setRecipes((r) => r.map((rec) => (rec.id === editing.id ? updated : rec)))
      } else {
        const created = await recipesApi.create(recipe)
        setRecipes((r) => [...r, created])
      }
    } catch (err) {
      console.error('Failed to save recipe', err)
    } finally {
      setShowModal(false)
      setEditing(null)
    }
  }

  const handleDelete = async (id) => {
    try {
      await recipesApi.delete(id)
      setRecipes((r) => r.filter((rec) => rec.id !== id))
    } catch (err) {
      console.error('Failed to delete recipe', err)
    }
  }

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BookmarkIcon className="h-5 w-5" /> Recipes
        </div>
        <div className="flex items-center gap-2">
          <Input placeholder="Search recipes…" className="w-56" />
          <Button
            variant="a1"
            onClick={() => {
              setEditing(null)
              setShowModal(true)
            }}
          >
            + New recipe
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {recipes.map((r) => (
          <Motion.div key={r.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            <div
              className="rounded-2xl border p-3 bg-white cursor-pointer"
              style={{ borderColor: 'var(--border)' }}
              onClick={() => toggle(r.id)}
            >
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium">
                    {r.title}
                    <span className="ml-1 text-xs text-[color:var(--text-subtle)]">
                      {(r.ingredients || []).length}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-[color:var(--text-subtle)]">
                    {r.course} • {r.score != null ? r.score.toFixed(2) : '0'}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {r.hot && <Badge tone="a2">hot</Badge>}
                  {(r.tags || []).map((t) => (
                    <Badge key={t} tone="a3">
                      <TagIcon className="h-3 w-3" />{t}
                    </Badge>
                  ))}
                </div>
              </div>

              {expanded === r.id && (
                <div className="mt-3">
                  <div className="text-sm font-medium mb-1">Ingredients</div>
                  <ul className="list-disc list-inside text-sm mb-2">
                    {(r.ingredients || []).map((ing, idx) => (
                      <li key={ing.id || idx}>
                        {[ing.amount, ing.unit, ing.name || ing]
                          .filter(Boolean)
                          .join(' ')}
                      </li>
                    ))}
                  </ul>
                  {r.procedure && (
                    <>
                      <div className="text-sm font-medium mb-1">Procedure</div>
                      <p className="text-sm mb-3">{r.procedure}</p>
                    </>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      variant="a2"
                      onClick={(e) => {
                        e.stopPropagation()
                        setEditing(r)
                        setShowModal(true)
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(r.id)
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </Motion.div>
        ))}
      </div>
      {showModal && (
        <NewRecipeModal
          onClose={() => {
            setShowModal(false)
            setEditing(null)
          }}
          onSave={handleSave}
          initialRecipe={editing}
        />
      )}
    </Card>
  )
}

