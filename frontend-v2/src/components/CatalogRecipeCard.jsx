import { BookmarkIcon } from '@heroicons/react/24/outline'
import { Badge } from './Badge'
import { Card } from './Card'
import { Icon } from './Icon'
import { courseColor, dishIcon } from '../constants/recipeIcons'

/**
 * The recipe image, or the course-coloured placeholder tile when there is none
 * (design guide §4.2). Fills its positioned parent.
 *
 * The same media the Recipes grid draws. `RecipesPage` keeps its own private
 * copy, which this task may not touch; folding the two together is left to the
 * final simplify pass.
 */
export function CatalogRecipeMedia({ recipe, rounded }) {
  const color = courseColor[recipe.course] || 'var(--c-a3)'
  const fill = { position: 'absolute', inset: 0, width: '100%', height: '100%', borderRadius: rounded }
  if (recipe.image_url) {
    return (
      <img src={recipe.image_url} alt={`${recipe.title} photo`} style={{ ...fill, objectFit: 'cover' }} />
    )
  }
  return (
    <div
      aria-hidden="true"
      style={{
        ...fill,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `linear-gradient(135deg, color-mix(in srgb, ${color} 24%, #fff), color-mix(in srgb, ${color} 8%, #fff))`,
      }}
    >
      <Icon set="mdi" name={dishIcon(recipe)} size={48} color={color} />
    </div>
  )
}

/**
 * One catalog recipe on the Discover grid.
 *
 * Two separate controls rather than one clickable card: the upper part is a
 * button that opens the detail view, and the footer holds the selection
 * checkbox. Nesting a checkbox inside a clickable card made every tick also
 * open the recipe, and put one interactive element inside another.
 *
 * A recipe already in the user's book has no checkbox at all (UI-9): it shows
 * "In your book" in the checkbox's place. The adoption count is an aggregate
 * number only, never who added it (UI-13).
 *
 * `disabled` locks the checkbox (but not the detail view) while the page's add
 * request is in flight, so the selection cannot change under it.
 */
export default function CatalogRecipeCard({ recipe, selected = false, disabled = false, onToggle, onOpen }) {
  const count = recipe.adoption_count ?? 0
  const ingredientCount = (recipe.ingredients || []).length

  return (
    <Card
      data-testid="catalog-card"
      className="flex flex-col overflow-hidden"
      style={{
        padding: 0,
        // A ring rather than a thicker border, so selecting does not reflow the grid.
        boxShadow: selected ? '0 0 0 2px var(--c-a2), var(--shadow-sm)' : 'var(--shadow-sm)',
      }}
    >
      <button
        type="button"
        onClick={onOpen}
        className="flex flex-1 cursor-pointer flex-col border-0 bg-transparent p-0 text-left"
      >
        <div style={{ position: 'relative', width: '100%', aspectRatio: '1 / 1' }}>
          <CatalogRecipeMedia recipe={recipe} />
          <div
            className="pointer-events-none absolute flex justify-between"
            style={{ top: 8, left: 8, right: 8 }}
          >
            <span
              className="flex items-center justify-center rounded-full bg-white"
              style={{ width: 26, height: 26, boxShadow: '0 1px 4px rgba(0,0,0,0.25)' }}
            >
              <Icon
                set="mdi"
                name={dishIcon(recipe)}
                size={15}
                color={courseColor[recipe.course] || 'var(--c-a3)'}
              />
            </span>
            {recipe.bulk_prep && (
              <img
                src="/assets/icons/bulk_icon.png"
                alt="bulk prep"
                style={{ height: 20, filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.35))' }}
              />
            )}
          </div>
        </div>
        <div className="flex w-full flex-1 flex-col gap-1.5" style={{ padding: 12 }}>
          <span
            className="line-clamp-2"
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 'var(--weight-semibold)',
              fontSize: 'var(--text-sm)',
              color: 'var(--text-strong)',
              lineHeight: 1.3,
            }}
          >
            {recipe.title}
          </span>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
            {`${recipe.course} · ${ingredientCount} ${ingredientCount === 1 ? 'ingredient' : 'ingredients'}`}
          </span>
          {(recipe.tags || []).length > 0 && (
            <span className="mt-auto flex flex-wrap gap-1">
              {recipe.tags.slice(0, 2).map((tag) => (
                <Badge key={tag} tone="caramel">
                  {tag}
                </Badge>
              ))}
            </span>
          )}
        </div>
      </button>

      <div
        className="flex min-h-11 flex-wrap items-center justify-between gap-2 border-t px-3"
        style={{ borderColor: 'var(--border-default)' }}
      >
        {recipe.in_my_book ? (
          <Badge tone="sage">In your book</Badge>
        ) : (
          // The whole label is the 44px target, not just the 20px box inside it.
          <label
            className={`flex min-h-11 min-w-0 items-center gap-2 ${disabled ? '' : 'cursor-pointer'}`}
            style={{ fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }}
          >
            <input
              type="checkbox"
              checked={selected}
              disabled={disabled}
              onChange={onToggle}
              aria-label={`Select ${recipe.title}`}
              className={`h-5 w-5 flex-shrink-0 ${disabled ? '' : 'cursor-pointer'}`}
              style={{ accentColor: 'var(--c-pos)' }}
            />
            Select
          </label>
        )}
        <span
          role="img"
          aria-label={`Added ${count} ${count === 1 ? 'time' : 'times'}`}
          title="Times added to a recipe book"
          className="inline-flex items-center gap-1"
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 'var(--weight-semibold)',
            color: 'var(--text-muted)',
          }}
        >
          {/* The book glyph the Recipes nav item wears: "added to a book". */}
          <BookmarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
          {count}
        </span>
      </div>
    </Card>
  )
}
