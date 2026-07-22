import React from 'react'
import { Card } from './Card'
import { Button } from './Button'
import {
  CheckIcon,
  XMarkIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'

/**
 * The week calendar grid: lunch/dinner rows for the current week, per-cell
 * accept/reject controls, and previous/next-week navigation. Presentational —
 * all state and actions come from props.
 */
export default function MealPlanCalendar({
  weekDays,
  plan,
  fmt,
  isToday,
  onSelectCell,
  onAccept,
  onReject,
  onChangeWeek,
  onArmSwap,
  armedCell,
}) {
  const renderCell = (d, idx) => {
    const iso = fmt(d)
    const meal = plan[iso]?.[idx]
    const armed =
      armedCell && armedCell.date === iso && armedCell.mealIndex === idx
    const acceptedStyle = meal?.accepted
      ? {
          backgroundColor: 'rgba(12, 58, 45, 0.15)',
          color: 'var(--text-strong)',
        }
      : {}
    // An armed cell (yellow) wins over the accepted/today tints.
    const armedStyle = armed
      ? { backgroundColor: 'rgba(255, 185, 2, 0.25)', color: 'var(--text-strong)' }
      : {}
    return (
      <div
        key={`${idx}-${iso}`}
        data-cell
        className="relative border p-2 h-24 cursor-pointer"
        onClick={() => onSelectCell({ date: iso, mealIndex: idx })}
        style={
          isToday(d)
            ? {
                borderColor: 'var(--border)',
                color: 'var(--text-strong)',
                ...(meal?.accepted
                  ? acceptedStyle
                  : { backgroundColor: 'rgba(187, 138, 82, 0.15)' }),
                ...armedStyle,
              }
            : { borderColor: 'var(--border)', ...acceptedStyle, ...armedStyle }
        }
      >
        {meal ? (
          <>
            <div className="text-sm font-medium">
              {meal.recipe}
              {meal.leftover && (
                <img
                  src="/assets/icons/left_overs_icon.png"
                  alt="Leftover"
                  className="inline ml-1 h-4 w-4"
                />
              )}
            </div>
            {meal.side_recipes && meal.side_recipes.length > 0 && (
              <div className="mt-1 text-xs">{meal.side_recipes.join(', ')}</div>
            )}
            <div className="absolute bottom-1 right-1 flex space-x-1">
              <ArrowsRightLeftIcon
                role="button"
                aria-label="Swap meal"
                className="h-4 w-4 text-[color:var(--c-a2)] cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation()
                  onArmSwap({ date: iso, mealIndex: idx })
                }}
              />
              {!meal.accepted && (
                <>
                  <XMarkIcon
                    className="h-4 w-4 text-[color:var(--c-neg)] cursor-pointer"
                    onClick={(e) => {
                      e.stopPropagation()
                      onReject({ date: iso, mealIndex: idx })
                    }}
                  />
                  <CheckIcon
                    className="h-4 w-4 text-[color:var(--c-pos)] cursor-pointer"
                    onClick={(e) => {
                      e.stopPropagation()
                      onAccept({ date: iso, mealIndex: idx })
                    }}
                  />
                </>
              )}
            </div>
          </>
        ) : (
          <div className="text-sm text-[color:var(--text-subtle)]">—</div>
        )}
      </div>
    )
  }

  return (
    <>
      <div className="flex justify-between">
        <Button variant="ghost" onClick={() => onChangeWeek(-1)}>
          Previous week
        </Button>
        <Button variant="ghost" onClick={() => onChangeWeek(1)}>
          Next week
        </Button>
      </div>
      <Card>
        <div className="grid grid-cols-8">
          <div />
          {weekDays.map((d) => {
            const weekday = d.toLocaleDateString(undefined, { weekday: 'short' })
            const dm = `${d.getDate()}/${d.getMonth() + 1}`
            return (
              <div
                key={d.toISOString()}
                className={`p-2 text-center ${
                  isToday(d) ? 'text-white rounded-t-lg' : ''
                }`}
                style={isToday(d) ? { backgroundColor: 'var(--c-a3)' } : undefined}
              >
                <div className="font-medium">{weekday}</div>
                <div className="text-sm">{dm}</div>
              </div>
            )
          })}
          <div className="p-2 text-left font-medium">Lunch</div>
          {weekDays.map((d) => renderCell(d, 0))}
          <div className="p-2 text-left font-medium">Dinner</div>
          {weekDays.map((d) => renderCell(d, 1))}
        </div>
      </Card>
    </>
  )
}
