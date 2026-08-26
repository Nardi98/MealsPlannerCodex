import React from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { useIsMobile } from '../hooks/useIsMobile'
import {
  CheckIcon,
  XMarkIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'

// Index 0/1 here are the backend's `meal_number` 1/2.
const MEAL_LABELS = ['Lunch', 'Dinner']

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
  const isMobile = useIsMobile()

  const days = React.useMemo(
    () =>
      weekDays.map((d) => ({
        date: d,
        key: d.toISOString(),
        short: d.toLocaleDateString(undefined, { weekday: 'short' }),
        long: d.toLocaleDateString(undefined, { weekday: 'long' }),
        dm: `${d.getDate()}/${d.getMonth() + 1}`,
        today: isToday(d),
      })),
    [weekDays, isToday],
  )

  // The day header's today-tint, which both layouts paint the same way.
  const todayTint = (today) => (today ? { backgroundColor: 'var(--c-a3)' } : undefined)

  // One cell carries the tutorial's anchor: the step explains what a cell is,
  // and the whole calendar is taller than the window on most screens.
  const renderCell = (d, idx, isTourAnchor = false) => {
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
        data-tour={isTourAnchor ? 'mealplan-cell' : undefined}
        className="relative border p-2 cursor-pointer min-h-16 md:h-24"
        onClick={() =>
          armedCell
            ? onArmSwap({ date: iso, mealIndex: idx })
            : onSelectCell({ date: iso, mealIndex: idx })
        }
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
      <div className="flex flex-wrap justify-between gap-2" data-tour="mealplan-week-nav">
        <Button variant="ghost" onClick={() => onChangeWeek(-1)}>
          Previous week
        </Button>
        <Button variant="ghost" onClick={() => onChangeWeek(1)}>
          Next week
        </Button>
      </div>
      <Card data-tour="mealplan-calendar">
        {isMobile ? (
          <div className="flex flex-col gap-3">
            {days.map((day, i) => (
              <div key={day.key} data-testid="mealplan-day" className="flex flex-col">
                <div
                  className={`px-2 py-1 rounded-t-lg font-medium ${day.today ? 'text-white' : ''}`}
                  style={todayTint(day.today)}
                >
                  {day.long} {day.dm}
                </div>
                {MEAL_LABELS.map((label, idx) => (
                  <div key={label}>
                    <div className="px-2 pt-2 text-xs uppercase tracking-wide text-[color:var(--text-subtle)]">
                      {label}
                    </div>
                    {renderCell(day.date, idx, i === 0 && idx === 0)}
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-8">
            <div />
            {days.map((day) => (
              <div
                key={day.key}
                className={`p-2 text-center ${day.today ? 'text-white rounded-t-lg' : ''}`}
                style={todayTint(day.today)}
              >
                <div className="font-medium">{day.short}</div>
                <div className="text-sm">{day.dm}</div>
              </div>
            ))}
            {MEAL_LABELS.map((label, idx) => (
              <React.Fragment key={label}>
                <div className="p-2 text-left font-medium">{label}</div>
                {days.map((day, i) => renderCell(day.date, idx, idx === 0 && i === 0))}
              </React.Fragment>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}
