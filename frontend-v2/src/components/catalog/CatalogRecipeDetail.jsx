import React from 'react'
import { Badge } from '../Badge'
import { Icon } from '../Icon'
import { Modal } from '../Modal'
import Quantity from '../Quantity'
import RecipeMedia from '../RecipeMedia'
import { catalogApi } from '../../api/catalogApi'
import { courseColor, dishIcon } from '../../constants/recipeIcons'
import { basisOf, peopleLabel } from '../../utils/servings'
import { useUnitSystem } from '../../hooks/useUnitSystem'
import { mutedTextStyle, sectionHeadingStyle } from './textStyles'

/**
 * The detail view of one catalog recipe: everything needed to decide (UI-7).
 *
 * Read-only, for every account. Curation happens on `CatalogAdminPage`, which
 * edits and retires from its listing rows and never opens this.
 */
export default function CatalogRecipeDetail({ recipe, onClose }) {
  const unitSystem = useUnitSystem()
  const [detail, setDetail] = React.useState(null)
  const [failed, setFailed] = React.useState(false)

  // Keyed by the parent on the recipe id, so this state starts fresh per recipe.
  React.useEffect(() => {
    let stale = false
    catalogApi
      .get(recipe.id)
      .then((row) => !stale && setDetail(row))
      .catch((err) => {
        console.error('Failed to load catalog recipe', err)
        if (!stale) setFailed(true)
      })
    return () => {
      stale = true
    }
  }, [recipe.id])

  // The listing row renders at once; the detail fills in ingredients and procedure.
  const shown = detail || recipe
  const servings = basisOf(shown.servings)

  return (
    <Modal title={shown.title} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <div style={{ position: 'relative', width: '100%', aspectRatio: '16 / 9', overflow: 'hidden' }}>
          <RecipeMedia recipe={shown} rounded="var(--radius-md)" />
        </div>
        <div
          className="flex items-center gap-1.5"
          style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}
        >
          <Icon set="mdi" name={dishIcon(shown)} size={16} color={courseColor[shown.course] || 'var(--c-a3)'} />
          {shown.course}
        </div>
        {(shown.bulk_prep || (shown.tags || []).length > 0) && (
          <div className="flex flex-wrap gap-1.5">
            {shown.bulk_prep && (
              <Badge tone="gold">
                <img src="/assets/icons/bulk_icon.png" alt="" style={{ height: 12 }} />
                bulk
              </Badge>
            )}
            {(shown.tags || []).map((tag) => (
              <Badge key={tag} tone="caramel">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        {failed && (
          <p role="alert" style={{ ...mutedTextStyle, color: 'var(--c-neg)' }}>
            Couldn&apos;t load this recipe. Close it and try again.
          </p>
        )}
        {!detail && !failed && <p style={mutedTextStyle}>Loading…</p>}
        {detail && (
          <div>
            <div style={sectionHeadingStyle}>
              Ingredients for {servings} {peopleLabel(servings)}
            </div>
            <ul style={{ margin: '0 0 12px', paddingLeft: 18, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
              {(detail.ingredients || []).map((ing, i) => (
                <li key={`${ing.name}-${i}`}>
                  <Quantity amount={ing.quantity} unit={ing.unit} system={unitSystem} /> {ing.name}
                </li>
              ))}
            </ul>
            {detail.procedure && (
              <>
                <div style={sectionHeadingStyle}>Procedure</div>
                <p style={{ margin: 0, whiteSpace: 'pre-line', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                  {detail.procedure}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
