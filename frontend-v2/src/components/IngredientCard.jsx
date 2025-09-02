import React from 'react'
import { Card, Button, SeasonalityGrid } from './'

export default function IngredientCard({ name, unit, season = [], onEdit, onDelete }) {
  const [expanded, setExpanded] = React.useState(false)

  const toggle = () => setExpanded((e) => !e)
  const handleEdit = (e) => {
    e.stopPropagation()
    onEdit?.()
  }
  const handleDelete = (e) => {
    e.stopPropagation()
    onDelete?.()
  }

  return (
    <Card className="h-full cursor-pointer" onClick={toggle}>
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
