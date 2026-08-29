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
import { PageTour } from '../tutorial/PageTour'
import {
  AttributionLine,
  FavoriteSidesSelect,
  ImportRecipeModal,
  NewRecipeModal,
  ShareRecipeModal,
} from '../components'
import { dishIcon, courseColor } from '../constants/recipeIcons'
import { basisOf, peopleLabel } from '../utils/servings'
import { useIsMobile } from '../hooks/useIsMobile'
import { recipesApi } from '../api/recipesApi'
import { tagsApi } from '../api/tagsApi'
import { ingredientsApi } from '../api/ingredientsApi'

// Only a main dish is served with a side. Mirrors the backend's
// COURSES_WITH_FAVORITE_SIDES (models.py), which rejects anything else.
const COURSES_WITH_SIDES = ['main']

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

// Lazy: the starter pack carries a 30 KB recipe catalogue that only a
// brand-new, empty account ever renders. Importing it through the barrel would
// put it in every page's bundle, login included.
const StarterRecipesModal = React.lazy(() => import('../components/StarterRecipesModal'))

const STARTER_DISMISSED_KEY = 'starterRecipesDismissed'

export default function RecipesPage() {
  const isMobile = useIsMobile()
  const [recipes, setRecipes] = React.useState([])
  const [opened, setOpened] = React.useState(null)
  const [showModal, setShowModal] = React.useState(false)
  const [showImport, setShowImport] = React.useState(false)
  // The starter-recipe offer (SR): shown once the first load comes back empty.
  // Dismissal lives in sessionStorage rather than on the account, so a user who
  // says "maybe later" is not asked again this session but is offered the pack
  // again next time they sign in with a book that is still empty.
  const [showStarter, setShowStarter] = React.useState(false)
  // The tutorial waits for this. `showStarter` is false until the first load
  // comes back, so gating the tour on it alone would let the tour open in front
  // of a starter modal that is about to appear.
  const [loaded, setLoaded] = React.useState(false)
  const [editing, setEditing] = React.useState(null)
  const [sharing, setSharing] = React.useState(false)
  // The share dialog belongs to whichever recipe is open; closing or switching
  // the detail modal must not carry it over to the next one.
  React.useEffect(() => {
    setSharing(false)
  }, [opened])
  const [search, setSearch] = React.useState('')
  const [showFilters, setShowFilters] = React.useState(false)
  const [tags, setTags] = React.useState([])
  // The account's full ingredient rows. The filter list needs only the names,
  // but the starter-pack import needs each row's id, unit and seasonality —
  // fetching them twice was the alternative.
  const [ingredientRows, setIngredientRows] = React.useState([])
  const ingredientNames = React.useMemo(
    () => ingredientRows.map((i) => i.name),
    [ingredientRows],
  )
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
        if (recipesRes.length === 0 && sessionStorage.getItem(STARTER_DISMISSED_KEY) !== '1') {
          setShowStarter(true)
        }
        setTags(tagsRes.map((t) => t.name))
        setIngredientRows(ingRes)
      } catch (err) {
        console.error('Failed to load recipes, tags or ingredients', err)
      } finally {
        setLoaded(true)
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

  // The sides a dish can be paired with, and whether it takes any at all. The
  // picker is only offered for courses that take sides, so a recipe can never
  // reach its own entry here.
  const sideOptions = React.useMemo(
    () =>
      recipes
        .filter((r) => r.course === 'side')
        .map((r) => ({ id: r.id, title: r.title })),
    [recipes]
  )
  const takesFavoriteSides = COURSES_WITH_SIDES.includes(openRecipe?.course)

  // Curating sides from the read-only detail view saves on each click, so the
  // list updates optimistically and rolls back if the write fails -- otherwise
  // the UI would show a pairing the server never stored.
  const handleFavoriteSidesChange = async (nextIds) => {
    const recipe = openRecipe
    if (!recipe) return
    const previous = recipe.favorite_side_ids || []
    const apply = (ids) =>
      setRecipes((rs) =>
        rs.map((r) => (r.id === recipe.id ? { ...r, favorite_side_ids: ids } : r))
      )
    apply(nextIds)
    try {
      // serialiseRecipe sends the whole recipe, so spread the rest of it in.
      const updated = await recipesApi.update(recipe.id, {
        ...recipe,
        favorite_side_ids: nextIds,
      })
      setRecipes((rs) => rs.map((r) => (r.id === recipe.id ? updated : r)))
    } catch (err) {
      console.error('Failed to update favorite sides', err)
      apply(previous)
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
      {/* Held back until the first load settles, so a brand-new account is
          offered the starter pack before being taught about the grid. */}
      <PageTour id="recipes" enabled={loaded && !showStarter} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Recipes
        </h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Button
              variant="ghost"
              aria-label="Filter"
              data-tour="recipes-filter"
              onClick={() => setShowFilters((s) => !s)}
              Icon={FunnelIcon}
            />
            {showFilters && (
              <div
                className="absolute right-0 z-10 mt-2 w-[min(14rem,calc(100vw-2rem))] rounded-2xl border bg-white p-2"
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
                  options={ingredientNames}
                  selected={selectedIngredients}
                  onSelect={toggleIngredient}
                />
              </div>
            )}
          </div>
          <Input
            placeholder="Search recipes…"
            data-tour="recipes-search"
            className="w-full sm:w-56"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button
            variant="ghost"
            data-tour="recipes-import"
            onClick={() => setShowImport(true)}
          >
            Import from web
          </Button>
          <Button
            variant="accent"
            data-tour="recipes-new"
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
        data-tour="recipes-grid"
        className="card-grid"
      >
        {filteredRecipes.map((r, i) => (
          <Card
            key={r.id}
            // The tour points at one card, not the grid: the grid is taller than
            // the window, and there is no room beside it for a bubble.
            data-tour={i === 0 ? 'recipes-card' : undefined}
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
                className="line-clamp-2"
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
              {/* Plain flowing text, not a flex row: flex makes each text run
                  an unbreakable item, so the line broke between "7" and
                  "ingredients" and stranded the portion count. */}
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                {isMobile
                  ? `${r.course} · ${(r.ingredients || []).length} ingr · ${basisOf(r.servings)}p`
                  : `${r.course} · ${(r.ingredients || []).length} ingredients · serves ${basisOf(r.servings)}`}
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
            {/* AT-3/AT-7: permanent credit when this recipe was copied. */}
            <AttributionLine recipe={openRecipe} />
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
              <div style={sectionHeadingStyle}>
                Ingredients for {basisOf(openRecipe.servings)}{' '}
                {peopleLabel(basisOf(openRecipe.servings))}
              </div>
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
            {takesFavoriteSides && (
              <div>
                <div style={sectionHeadingStyle}>Favorite sides</div>
                <p
                  style={{
                    margin: '0 0 8px',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--text-muted)',
                  }}
                >
                  One of these is added automatically when this dish is planned.
                </p>
                <FavoriteSidesSelect
                  options={sideOptions}
                  selected={openRecipe.favorite_side_ids || []}
                  onChange={handleFavoriteSidesChange}
                />
              </div>
            )}
            <div className="flex justify-end gap-2">
              {/* SH-12: the share control lives in the existing detail modal. */}
              <Button size="sm" variant="secondary" onClick={() => setSharing(true)}>
                Share
              </Button>
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

      {openRecipe && (
        <ShareRecipeModal
          recipe={openRecipe}
          open={sharing}
          onClose={() => setSharing(false)}
        />
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

      {showStarter && (
        <React.Suspense fallback={null}>
          <StarterRecipesModal
            ingredients={ingredientRows}
            onClose={() => {
              sessionStorage.setItem(STARTER_DISMISSED_KEY, '1')
              setShowStarter(false)
            }}
            onImported={async () => {
              setShowStarter(false)
              setRecipes(await recipesApi.fetchAll())
            }}
          />
        </React.Suspense>
      )}

      {showImport && (
        <ImportRecipeModal
          onClose={() => setShowImport(false)}
          onCreated={(created) => {
            setRecipes((r) => [...r, created])
            setShowImport(false)
          }}
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
