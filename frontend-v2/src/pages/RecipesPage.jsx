import React from 'react'
import { BookmarkIcon, TagIcon, PlusIcon } from '@heroicons/react/24/outline'
import { motion as Motion } from 'framer-motion'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export default function RecipesPage() {
  const [recipes, setRecipes] = React.useState([])
  const [expanded, setExpanded] = React.useState(null)

  React.useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE_URL}/recipes`)
        const data = await res.json()
        setRecipes(data)
      } catch (err) {
        console.error('Failed to load recipes', err)
      }
    }
    load()
  }, [])

  const toggle = (id) => setExpanded(expanded === id ? null : id)

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BookmarkIcon className="h-5 w-5" /> Recipes
        </div>
        <div className="flex items-center gap-2">
          <Input placeholder="Search recipes…" className="w-56" />
          <Button variant="a1" Icon={PlusIcon}>New recipe</Button>
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
                  <div className="font-medium">{r.title}</div>
                  <div className="mt-0.5 text-xs text-[color:var(--text-subtle)]">
                    {r.course} • {r.score != null ? r.score.toFixed(2) : '0'}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {r.hot && <Badge tone="a2">hot</Badge>}
                  {(r.tags || []).map((t) => (
                    <Badge key={t.id || t.name || t} tone="a3">
                      <TagIcon className="h-3 w-3" />{t.name || t}
                    </Badge>
                  ))}
                </div>
              </div>

              {expanded === r.id && (
                <div className="mt-3">
                  <div className="text-sm font-medium mb-1">Ingredients</div>
                  <ul className="list-disc list-inside text-sm mb-2">
                    {(r.ingredients || []).map((ing) => (
                      <li key={ing.id}>{ing.name}</li>
                    ))}
                  </ul>
                  {r.procedure && (
                    <>
                      <div className="text-sm font-medium mb-1">Procedure</div>
                      <p className="text-sm mb-3">{r.procedure}</p>
                    </>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="a2" onClick={(e) => e.stopPropagation()}>Edit</Button>
                    <Button size="sm" variant="danger" onClick={(e) => e.stopPropagation()}>Delete</Button>
                  </div>
                </div>
              )}
            </div>
          </Motion.div>
        ))}
      </div>
    </Card>
  )
}

