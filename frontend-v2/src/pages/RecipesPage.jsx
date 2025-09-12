import React from 'react'
import {
  BookmarkIcon,
  TagIcon,
  FunnelIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline'
import { motion as Motion } from 'framer-motion'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { NewRecipeModal } from '../components'
import { recipesApi } from '../api/recipesApi'
import { tagsApi } from '../api/tagsApi'
import { ingredientsApi } from '../api/ingredientsApi'

export default function RecipesPage() {
  const [recipes, setRecipes] = React.useState([])
  const [expanded, setExpanded] = React.useState(null)
  const [showModal, setShowModal] = React.useState(false)
  const [editing, setEditing] = React.useState(null)
  const [search, setSearch] = React.useState('')
  const [showFilters, setShowFilters] = React.useState(false)
  const [tags, setTags] = React.useState([])
  const [ingredients, setIngredients] = React.useState([])
  const [selectedTags, setSelectedTags] = React.useState([])
  const [selectedIngredients, setSelectedIngredients] = React.useState([])
  const [selectedCourses, setSelectedCourses] = React.useState([])
  const [tagsOpen, setTagsOpen] = React.useState(false)
  const [ingredientsOpen, setIngredientsOpen] = React.useState(false)
  const [coursesOpen, setCoursesOpen] = React.useState(false)

  React.useEffect(() => {
    async function load() {
      try {
        const [recipesRes, tagsRes, ingRes] = await Promise.all([
          recipesApi.fetchAll(),
          tagsApi.fetchAll(),
          ingredientsApi.fetchAll(),
        ])
        setRecipes(recipesRes)
        setTags(tagsRes.map((t) => t.name))
        setIngredients(ingRes.map((i) => i.name))
      } catch (err) {
        console.error('Failed to load recipes, tags or ingredients', err)
      }
    }
    load()
  }, [])

  const toggle = (id) => setExpanded(expanded === id ? null : id)

  const filteredRecipes = React.useMemo(
    () =>
      recipes.filter((r) => {
        const matchesSearch = r.title
          ?.toLowerCase()
          .includes(search.toLowerCase())
        const matchesTags = selectedTags.every((t) => r.tags?.includes(t))
        const matchesIngredients = selectedIngredients.every((i) =>
          r.ingredients?.some((ing) => (ing.name || ing) === i)
        )
        const matchesCourses =
          selectedCourses.length === 0 || selectedCourses.includes(r.course)
        return (
          matchesSearch &&
          matchesTags &&
          matchesIngredients &&
          matchesCourses
        )
      }),
    [recipes, search, selectedTags, selectedIngredients, selectedCourses]
  )

  const courseOptions = React.useMemo(
    () => Array.from(new Set(recipes.map((r) => r.course))).filter(Boolean),
    [recipes]
  )

  const toggleTag = (tag) =>
    setSelectedTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag]
    )

  const toggleIngredient = (ing) =>
    setSelectedIngredients((ings) =>
      ings.includes(ing)
        ? ings.filter((x) => x !== ing)
        : [...ings, ing]
    )

  const toggleCourse = (course) =>
    setSelectedCourses((cs) =>
      cs.includes(course) ? cs.filter((c) => c !== course) : [...cs, course]
    )

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
          <div className="relative">
            <Button
              variant="ghost"
              aria-label="Filter"
              onClick={() => setShowFilters((s) => !s)}
              Icon={FunnelIcon}
            />
            {showFilters && (
              <div
                className="absolute z-10 mt-2 w-56 rounded-2xl border bg-white p-2"
                style={{ borderColor: 'var(--border)' }}
              >
                <div>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-sm"
                    onClick={() => setCoursesOpen((o) => !o)}
                  >
                    Course
                    <ChevronDownIcon
                      className={`h-4 w-4 transition-transform ${
                        coursesOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {coursesOpen && (
                    <div className="mt-1 max-h-40 overflow-y-auto">
                      {courseOptions.map((c) => (
                        <label key={c} className="flex items-center gap-1 text-sm">
                          <input
                            type="checkbox"
                            checked={selectedCourses.includes(c)}
                            onChange={() => toggleCourse(c)}
                          />
                          {c}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
                <div className="mt-2">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-sm"
                    onClick={() => setTagsOpen((o) => !o)}
                  >
                    Tags
                    <ChevronDownIcon
                      className={`h-4 w-4 transition-transform ${
                        tagsOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {tagsOpen && (
                    <div className="mt-1 max-h-40 overflow-y-auto">
                      {tags.map((t) => (
                        <label key={t} className="flex items-center gap-1 text-sm">
                          <input
                            type="checkbox"
                            checked={selectedTags.includes(t)}
                            onChange={() => toggleTag(t)}
                          />
                          {t}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
                <div className="mt-2">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-sm"
                    onClick={() => setIngredientsOpen((o) => !o)}
                  >
                    Ingredients
                    <ChevronDownIcon
                      className={`h-4 w-4 transition-transform ${
                        ingredientsOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {ingredientsOpen && (
                    <div className="mt-1 max-h-40 overflow-y-auto">
                      {ingredients.map((i) => (
                        <label key={i} className="flex items-center gap-1 text-sm">
                          <input
                            type="checkbox"
                            checked={selectedIngredients.includes(i)}
                            onChange={() => toggleIngredient(i)}
                          />
                          {i}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          <Input
            placeholder="Search recipes…"
            className="w-56"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
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
        {filteredRecipes.map((r) => (
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
                  {r.hot && (
                    <Badge tone="a1">
                      <img
                        src="/assets/icons/bulk_icon.png"
                        alt="bulk prep"
                        className="h-3 w-3"
                      />
                      bulk
                    </Badge>
                  )}
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

