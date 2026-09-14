import { Icon } from './Icon'
import { courseColor, dishIcon } from '../constants/recipeIcons'

/**
 * The recipe image, or the course-coloured placeholder tile when there is none
 * (design guide §4.2). Fills its positioned parent.
 *
 * Shared by the Recipes grid and detail view and by Discover's cards and
 * detail view, so a recipe looks the same in the book and in the library.
 */
export default function RecipeMedia({ recipe, rounded }) {
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
