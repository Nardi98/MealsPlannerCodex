import React from 'react'
import {
  FunnelIcon,
  ChevronDownIcon,
  PlusIcon,
} from '@heroicons/react/24/outline'
import { Input } from '../components/Input'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { Card } from '../components/Card'
import { Icon } from '../components/Icon'
import { Modal } from '../components/Modal'
import { NewRecipeModal } from '../components'
import { dishIcon, courseColor } from '../constants/recipeIcons'
import { recipesApi } from '../api/recipesApi'
import { tagsApi } from '../api/tagsApi'
import { ingredientsApi } from '../api/ingredientsApi'

const sectionHeadingStyle = {
  fontSize: 'var(--text-sm)',
  fontWeight: 'var(--weight-semibold)',
  marginBottom: 6,
  color: 'var(--text-strong)',
}

function RecipeMedia({ recipe, rounded }) {
  const color = courseColor[recipe.course] || 'var(--c-a3)'
  if (recipe.image_url) {
    return (
      <img
        src={recipe.image_url}
        alt={`${recipe.title} photo`}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          borderRadius: rounded,
        }}
      />
    )
  }
  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: rounded,
        background: `linear-gradient(135deg, color-mix(in srgb, ${color} 24%, #fff), color-mix(in srgb, ${color} 8%, #fff))`,
      }}
    >
      <Icon set="mdi" name={dishIcon(recipe)} size={48} color={color} />
    </div>
  )
}

export default function RecipesPage() {
  const [recipes, setRecipes] = React.useState([])
  const [opened, setOpened] = React.useState(null)
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
        return matchesSearch && matchesTags && matchesIngredients && matchesCourses
      }),
    [recipes, search, selectedTags, selectedIngredients, selectedCourses]
  )

  const courseOptions = React.useMemo(
    () => Array.from(new Set(recipes.map((r) => r.course))).filter(Boolean),
    [recipes]
  )

  const openRecipe = filteredRecipes.find((r) => r.id === opened)

  const toggleTag = (tag) =>
    setSelectedTags((t) => (t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag]))
  const toggleIngredient = (ing) =>
    setSelectedIngredients((ings) =>
      ings.includes(ing) ? ings.filter((x) => x !== ing) : [...ings, ing]
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
    } finally {
      setOpened(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Recipes
        </h1>
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
                style={{ borderColor: 'var(--border-default)' }}
              >
                <FilterGroup
                  label="Course"
                  open={coursesOpen}
                  onToggle={() => setCoursesOpen((o) => !o)}
                  options={courseOptions}
                  selected={selectedCourses}
                  onSelect={toggleCourse}
                />
                <FilterGroup
                  label="Tags"
                  open={tagsOpen}
                  onToggle={() => setTagsOpen((o) => !o)}
                  options={tags}
                  selected={selectedTags}
                  onSelect={toggleTag}
                />
                <FilterGroup
                  label="Ingredients"
                  open={ingredientsOpen}
                  onToggle={() => setIngredientsOpen((o) => !o)}
                  options={ingredients}
                  selected={selectedIngredients}
                  onSelect={toggleIngredient}
                />
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
            variant="accent"
            Icon={PlusIcon}
            onClick={() => {
              setEditing(null)
              setShowModal(true)
            }}
          >
            New recipe
          </Button>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          gap: 16,
        }}
      >
        {filteredRecipes.map((r) => (
          <Card
            key={r.id}
            onClick={() => setOpened(r.id)}
            className="flex cursor-pointer flex-col overflow-hidden"
            style={{ padding: 0 }}
          >
            <div style={{ position: 'relative', width: '100%', aspectRatio: '1 / 1' }}>
              <RecipeMedia recipe={r} />
              <div
                style={{
                  position: 'absolute',
                  top: 8,
                  left: 8,
                  right: 8,
                  display: 'flex',
                  justifyContent: 'space-between',
                  pointerEvents: 'none',
                }}
              >
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    background: '#fff',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
                  }}
                >
                  <Icon
                    set="mdi"
                    name={dishIcon(r)}
                    size={15}
                    color={courseColor[r.course] || 'var(--c-a3)'}
                  />
                </span>
                {r.hot && (
                  <img
                    src="/assets/icons/bulk_icon.png"
                    alt="bulk prep"
                    style={{ height: 20, filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.35))' }}
                  />
                )}
              </div>
            </div>
            <div className="flex flex-1 flex-col gap-1.5" style={{ padding: 12 }}>
              <div
                style={{
                  fontFamily: 'var(--font-display)',
                  fontWeight: 'var(--weight-semibold)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--text-strong)',
                  lineHeight: 1.3,
                }}
              >
                {r.title}
              </div>
              <div
                className="flex items-center gap-1"
                style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}
              >
                {r.course} · {(r.ingredients || []).length} ingredients
              </div>
              <div className="mt-auto flex flex-wrap gap-1">
                {(r.tags || []).slice(0, 2).map((t) => (
                  <Badge key={t} tone="caramel">
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {openRecipe && (
        <Modal title={openRecipe.title} onClose={() => setOpened(null)}>
          <div className="flex flex-col gap-3">
            <div
              style={{ position: 'relative', width: '100%', aspectRatio: '16 / 9', overflow: 'hidden' }}
            >
              <RecipeMedia recipe={openRecipe} rounded="var(--radius-md)" />
            </div>
            <div
              className="flex items-center gap-1.5"
              style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}
            >
              <Icon
                set="mdi"
                name={dishIcon(openRecipe)}
                size={16}
                color={courseColor[openRecipe.course] || 'var(--c-a3)'}
              />
              {openRecipe.course}
            </div>
            {(openRecipe.hot || (openRecipe.tags || []).length > 0) && (
              <div className="flex flex-wrap gap-1.5">
                {openRecipe.hot && (
                  <Badge tone="gold">
                    <img src="/assets/icons/bulk_icon.png" alt="" style={{ height: 12 }} />
                    bulk
                  </Badge>
                )}
                {(openRecipe.tags || []).map((t) => (
                  <Badge key={t} tone="caramel">
                    {t}
                  </Badge>
                ))}
              </div>
            )}
            <div>
              <div style={sectionHeadingStyle}>Ingredients</div>
              <ul
                style={{
                  margin: '0 0 12px',
                  paddingLeft: 18,
                  fontSize: 'var(--text-sm)',
                  color: 'var(--text-muted)',
                }}
              >
                {(openRecipe.ingredients || []).map((ing, i) => (
                  <li key={ing.id || i}>
                    {[ing.amount, ing.unit, ing.name || ing].filter(Boolean).join(' ')}
                  </li>
                ))}
              </ul>
              {openRecipe.procedure && (
                <>
                  <div style={sectionHeadingStyle}>Procedure</div>
                  <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                    {openRecipe.procedure}
                  </p>
                </>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <Button
                size="sm"
                variant="accent"
                onClick={() => {
                  setEditing(openRecipe)
                  setShowModal(true)
                  setOpened(null)
                }}
              >
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => handleDelete(openRecipe.id)}>
                Delete
              </Button>
            </div>
          </div>
        </Modal>
      )}

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
    </div>
  )
}

function FilterGroup({ label, open, onToggle, options, selected, onSelect }) {
  return (
    <div className="mt-2 first:mt-0">
      <button
        type="button"
        className="flex w-full items-center justify-between text-sm"
        onClick={onToggle}
      >
        {label}
        <ChevronDownIcon
          className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="mt-1 max-h-40 overflow-y-auto">
          {options.map((o) => (
            <label key={o} className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={selected.includes(o)}
                onChange={() => onSelect(o)}
              />
              {o}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
