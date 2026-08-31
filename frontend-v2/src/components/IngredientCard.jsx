import React from 'react'
import { Card, Button, SeasonalityGrid, Badge } from './'
import { BASE_UNITS, reachableDimensions } from '../utils/units'

/**
 * Displays an ingredient and optionally shows its details when expanded.
 *
 * The component can operate in a controlled or uncontrolled mode. When the
 * `expanded` prop is provided, the parent component controls the expanded
 * state and should also supply an `onToggle` handler. If `expanded` is omitted
 * the card manages its own state internally.
 */
export default function IngredientCard({
  name,
  grams_per_ml = null,
  grams_per_piece = null,
  season = [],
  categories = [],
  expanded: expandedProp,
  onToggle,
  onEdit,
  onDelete,
}) {
  // What this ingredient can be expressed in, derived from its conversions
  // rather than stored. A single-dimension ingredient is a normal ingredient,
  // so there is no warning state and nothing to complete.
  const measures = reachableDimensions({ grams_per_ml, grams_per_piece })

  const [internalExpanded, setInternalExpanded] = React.useState(false)
  const isControlled = expandedProp !== undefined
  const expanded = isControlled ? expandedProp : internalExpanded

  const toggle = () => {
    if (isControlled) {
      onToggle?.()
    } else {
      setInternalExpanded((e) => !e)
    }
  }

  const handleEdit = (e) => {
    e.stopPropagation()
    onEdit?.()
  }
  const handleDelete = (e) => {
    e.stopPropagation()
    onDelete?.()
  }

  return (
    <Card className="cursor-pointer" onClick={toggle}>
      <div className="text-sm font-medium" style={{ color: 'var(--text-strong)' }}>
        {name}
      </div>
      {expanded && (
        <div className="mt-3 flex flex-col gap-2">
          {measures.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {measures.map((dimension) => (
                <Badge key={dimension} tone="a1">
                  {BASE_UNITS[dimension]}
                </Badge>
              ))}
            </div>
          )}
          <SeasonalityGrid months={season} />
          {categories.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {categories.map((c) => (
                <Badge key={c} tone="a2">
                  {c}
                </Badge>
              ))}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2 mt-auto">
            <Button size="sm" variant="a2" onClick={handleEdit}>
              Edit
            </Button>
            <Button size="sm" variant="danger" onClick={handleDelete}>
              Delete
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
