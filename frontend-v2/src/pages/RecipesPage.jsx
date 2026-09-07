import React from 'react'
import {
  FunnelIcon,
  GlobeAltIcon,
  PencilSquareIcon,
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
  ActiveFilterChips,
  AttributionLine,
  BottomSheet,
  ConfirmModal,
  Fab,
  FavoriteSidesSelect,
  ImportRecipeModal,
  NewRecipeModal,
  RecipeFilters,
  RecipeSort,
  ShareRecipeModal,
} from '../components'
import { dishIcon, courseColor } from '../constants/recipeIcons'
import { basisOf, peopleLabel } from '../utils/servings'
import { defaultDirectionFor, sortRecipes } from '../utils/sortRecipes'
import Quantity from '../components/Quantity'
import { alternateForms } from '../utils/units'
import { useUnitSystem } from '../hooks/useUnitSystem'
import { useEscapeKey } from '../hooks/useEscapeKey'
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

// The learned preference score, always two decimals so the corner pill keeps a
// stable width across the grid.
const formatScore = (score) => Number(score ?? 0).toFixed(2)

// Not a Badge: badge tones are translucent, and this one has to stay readable
// sitting on top of the tags it overlaps.
const scorePillStyle = {
  position: 'absolute',
  right: 8,
  bottom: 8,
  zIndex: 1,
  pointerEvents: 'none',
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  boxShadow: 'var(--shadow-sm)',
  borderRadius: 999,
  padding: '1px 7px',
  fontSize: 'var(--text-xs)',
  fontWeight: 'var(--weight-semibold)',
  color: 'var(--text-muted)',
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
  const unitSystem = useUnitSystem()
  const isMobile = useIsMobile()
  const [recipes, setRecipes] = React.useState([])
  const [opened, setOpened] = React.useState(null)
  const [showModal, setShowModal] = React.useState(false)
  const [showImport, setShowImport] = React.useState(false)
  const [showAddSheet, setShowAddSheet] = React.useState(false)
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
  const [confirmingDelete, setConfirmingDelete] = React.useState(false)
  // The share dialog belongs to whichever recipe is open; closing or switching
  // the detail modal must not carry it over to the next one.
  React.useEffect(() => {
    setSharing(false)
    setConfirmingDelete(false)
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
  const [sortKey, setSortKey] = React.useState('default')
  const [sortDirection, setSortDirection] = React.useState(defaultDirectionFor('default'))

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

  // Sorting sits after filtering so the two compose: the user orders what the
  // filters left, not the whole catalogue.
  const sortedRecipes = React.useMemo(
    () => sortRecipes(filteredRecipes, { key: sortKey, direction: sortDirection }),
    [filteredRecipes, sortKey, sortDirection]
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

  // One list drives the popover, the sheet and the active-filter chips, so a
  // new group cannot be added to one surface and forgotten on the others.
  const filterGroups = React.useMemo(
    () => [
      {
        label: 'Course',
        options: courseOptions,
        selected: selectedCourses,
        onSelect: toggleCourse,
        clear: () => setSelectedCourses([]),
      },
      {
        label: 'Tags',
        options: tags,
        selected: selectedTags,
        onSelect: toggleTag,
        clear: () => setSelectedTags([]),
      },
      {
        label: 'Ingredients',
        options: ingredientNames,
        selected: selectedIngredients,
        onSelect: toggleIngredient,
        clear: () => setSelectedIngredients([]),
        // The only group long enough to need it: course and tags are a handful
        // each, while this is the account's whole catalogue.
        searchable: true,
      },
    ],
    [courseOptions, selectedCourses, tags, selectedTags, ingredientNames, selectedIngredients],
  )

  // Derived from the same list, so a group cannot be filtered on without also
  // being explained here.
  const activeFilters = React.useMemo(
    () =>
      filterGroups.flatMap(({ selected, onSelect }) =>
        selected.map((value) => ({ value, onRemove: () => onSelect(value) })),
      ),
    [filterGroups],
  )

  // Derived from the group list too: a fourth filter could otherwise be added
  // above and silently survive "clear all".
  const clearAllFilters = () => filterGroups.forEach((group) => group.clear())

  // The popover had no way out but the funnel itself. DateRangePicker two
  // files away already dismisses on outside-click and Escape; this is that.
  const filterRef = React.useRef(null)
  const closeFilters = React.useCallback(() => setShowFilters(false), [])
  // The sheet handles its own Escape; this is only for the desktop popover.
  useEscapeKey(showFilters && !isMobile, closeFilters)
  React.useEffect(() => {
    if (!showFilters || isMobile) return undefined
    const onDown = (e) => {
      if (filterRef.current && !filterRef.current.contains(e.target)) setShowFilters(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [showFilters, isMobile])

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
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative" ref={filterRef}>
            <Button
              variant="ghost"
              aria-label="Filter"
              data-tour="recipes-filter"
              className="relative"
              onClick={() => setShowFilters((s) => !s)}
              Icon={FunnelIcon}
            >
              {activeFilters.length > 0 && (
                <span
                  className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs"
                  style={{ backgroundColor: 'var(--c-neg)', color: '#fff' }}
                >
                  {activeFilters.length}
                </span>
              )}
            </Button>
            {showFilters && !isMobile && (
              <div
                // 20rem, up from 14: the chips inside grew from 13px checkboxes to
                // `px-4 min-h-11`, and a long ingredient name wrapped three
                // times in 224px. Still clamped to the viewport, per §8.
                className="absolute right-0 z-10 mt-2 w-[min(20rem,calc(100vw-2rem))] rounded-2xl border bg-white p-2"
                style={{ borderColor: 'var(--border-default)' }}
              >
                <RecipeFilters groups={filterGroups} />
              </div>
            )}
          </div>
          {/* `min-w-0` is the fix for the squeezed row: without it a flex
              item refuses to go below its content width, so the input claimed
              the row and then starved every button beside it. */}
          <Input
            placeholder="Search recipes…"
            data-tour="recipes-search"
            className="min-w-0 flex-1 md:w-56 md:flex-none"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <RecipeSort
            sortKey={sortKey}
            direction={sortDirection}
            onChange={(key, direction) => {
              setSortKey(key)
              setSortDirection(direction)
            }}
            onDirectionChange={setSortDirection}
          />
          {!isMobile && (
            <>
              <Button
                variant="ghost"
                data-tour="recipes-import"
                className="whitespace-nowrap"
                onClick={() => setShowImport(true)}
              >
                Import from web
              </Button>
              <Button
                variant="accent"
                data-tour="recipes-new"
                Icon={PlusIcon}
                className="whitespace-nowrap"
                onClick={() => {
                  setEditing(null)
                  setShowModal(true)
                }}
              >
                New recipe
              </Button>
            </>
          )}
        </div>
      </div>

      <ActiveFilterChips filters={activeFilters} onClearAll={clearAllFilters} />

      <div
        data-tour="recipes-grid"
        className="card-grid pb-24 md:pb-0"
      >
        {sortedRecipes.map((r, i) => (
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
            <div
              className="flex flex-1 flex-col gap-1.5"
              style={{ padding: 12, position: 'relative' }}
            >
              <div
                className="line-clamp-2"
                data-testid="recipe-title"
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
              <div className="mt-auto flex flex-wrap gap-1" style={{ paddingRight: 48 }}>
                {(r.tags || []).slice(0, 2).map((t) => (
                  <Badge key={t} tone="caramel">
                    {t}
                  </Badge>
                ))}
              </div>
              {/* Painted last, over the tags: a long tag row would otherwise
                  push the score out of the corner, so it sits on top with an
                  opaque background instead of reflowing. */}
              <span title="Score" style={scorePillStyle}>
                {formatScore(r.score)}
              </span>
            </div>
          </Card>
        ))}
      </div>

      {/* Held back on a brand-new account, which gets the starter-pack offer
          instead -- two empty states firing at once is worse than none. */}
      {loaded && recipes.length > 0 && filteredRecipes.length === 0 && (
        <div
          className="flex flex-col items-center gap-3 py-12 text-center"
          style={{ color: 'var(--text-subtle)' }}
        >
          <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
            No recipes match your search.
          </p>
          {(activeFilters.length > 0 || search) && (
            <Button
              variant="ghost"
              onClick={() => {
                setSearch('')
                clearAllFilters()
              }}
            >
              Clear search and filters
            </Button>
          )}
        </div>
      )}

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
              {openRecipe.course} · {formatScore(openRecipe.score)}
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
                    <Quantity
                      amount={ing.amount}
                      unit={ing.unit}
                      alternates={alternateForms(ing.amount, ing.unit, ing)}
                      system={unitSystem}
                    />{' '}
                    {ing.name || ing}
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
              <Button variant="secondary" onClick={() => setSharing(true)}>
                Share
              </Button>
              <Button
                variant="accent"
                onClick={() => {
                  setEditing(openRecipe)
                  setShowModal(true)
                  setOpened(null)
                }}
              >
                Edit
              </Button>
            </div>
            {/* Separated from the pair above and guarded: this is the one
                action in the app with no undo, and it used to sit on a 36px
                target immediately beside Edit. */}
            <div
              className="mt-1 border-t pt-3"
              style={{ borderColor: 'var(--border-default)' }}
            >
              <Button
                variant="ghost"
                className="w-full"
                style={{ color: 'var(--c-neg)' }}
                onClick={() => setConfirmingDelete(true)}
              >
                Delete
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {openRecipe && confirmingDelete && (
        <ConfirmModal
          title={`Delete ${openRecipe.title}?`}
          message="This can't be undone."
          confirmLabel="Delete recipe"
          onConfirm={() => {
            setConfirmingDelete(false)
            handleDelete(openRecipe.id)
          }}
          onCancel={() => setConfirmingDelete(false)}
        />
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

      {isMobile && (
        <Fab
          Icon={PlusIcon}
          label="Add a recipe"
          data-tour="recipes-new"
          onClick={() => setShowAddSheet(true)}
        />
      )}

      {showAddSheet && (
        <BottomSheet title="Add a recipe" onClose={() => setShowAddSheet(false)}>
          <div className="flex flex-col gap-2 pb-2">
            <Button
              variant="accent"
              Icon={PencilSquareIcon}
              className="w-full justify-start"
              onClick={() => {
                setShowAddSheet(false)
                setEditing(null)
                setShowModal(true)
              }}
            >
              Write it myself
            </Button>
            <Button
              variant="ghost"
              Icon={GlobeAltIcon}
              className="w-full justify-start"
              data-tour="recipes-import"
              onClick={() => {
                setShowAddSheet(false)
                setShowImport(true)
              }}
            >
              Import from a website
            </Button>
          </div>
        </BottomSheet>
      )}

      {showFilters && isMobile && (
        <BottomSheet
          title="Filters"
          onClose={() => setShowFilters(false)}
          footer={
            <Button
              variant="accent"
              className="w-full"
              onClick={() => setShowFilters(false)}
            >
              {`Show ${filteredRecipes.length} ${
                filteredRecipes.length === 1 ? 'recipe' : 'recipes'
              }`}
            </Button>
          }
        >
          <RecipeFilters groups={filterGroups} />
        </BottomSheet>
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
