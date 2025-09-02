import React from 'react'
import { Card, Button, SeasonalityGrid } from './'

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
  unit,
  season = [],
  expanded: expandedProp,
  onToggle,
  onEdit,
  onDelete,
}) {
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
          <div className="text-xs" style={{ color: 'var(--text-subtle)' }}>
            Unit: {unit}
          </div>
          <SeasonalityGrid months={season} />
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
