import React from 'react'
import { Card } from './Card'
import { useIsMobile } from '../hooks/useIsMobile'
import MealCard from './MealCard'
import MealStatusChip from './MealStatusChip'
import SwapBanner from './SwapBanner'
import CalendarWeekHeader from './CalendarWeekHeader'
import CalendarDayStrip from './CalendarDayStrip'
import {
  CheckIcon,
  XMarkIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'

// Index 0/1 here are the backend's `meal_number` 1/2.
const MEAL_LABELS = ['Lunch', 'Dinner']

// Which mobile layout was last used. Someone who plans in Week view should not
// be dropped back into Day view on every visit.
const VIEW_KEY = 'mp.calendarView'

function readStoredView() {
  try {
    const stored = window.localStorage.getItem(VIEW_KEY)
    return stored === 'week' ? 'week' : 'day'
  } catch {
    // Private mode / blocked storage: fall back to the default rather than
    // taking the calendar down with it.
    return 'day'
  }
}

/**
 * The week calendar. Presentational — all state and actions come from props.
 *
 * Below `md` this is a Day view (one day at a time, navigated by a seven-day
 * strip that doubles as the week overview) with an opt-in Week view for
 * reviewing a whole generated plan. At `md` and above it stays the seven-column
 * grid. Both layouts share the status chips, the explicit swap banner, and
 * 44px controls.
 *
 * The `useIsMobile` branch is deliberate and sanctioned by design guide §8.3:
 * the two layouts are genuinely different markup, not one grid restyled.
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
  onCancelSwap,
  onToday,
  armedCell,
}) {
  const isMobile = useIsMobile()
  const [view, setView] = React.useState(readStoredView)

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

  const todayDay = days.find((d) => d.today)
  const [selectedKey, setSelectedKey] = React.useState(null)
  // Follow the viewed week: land on today when it is in range, else day one.
  const activeKey =
    days.some((d) => d.key === selectedKey)
      ? selectedKey
      : (todayDay?.key ?? days[0]?.key)
  const activeDay = days.find((d) => d.key === activeKey)

  const changeView = (next) => {
    setView(next)
    try {
      window.localStorage.setItem(VIEW_KEY, next)
    } catch {
      // Storage is a convenience here; losing it must not break the toggle.
    }
  }

  const mealAt = (date, idx) => plan[fmt(date)]?.[idx]
  const mealsFor = (date) =>
    MEAL_LABELS.map((_, idx) => mealAt(date, idx)).filter(Boolean)

  const isArmed = (iso, idx) =>
    Boolean(armedCell && armedCell.date === iso && armedCell.mealIndex === idx)

  const armedMeal = armedCell
    ? plan[armedCell.date]?.[armedCell.mealIndex]
    : null

  // The day header's today-tint, which both layouts paint the same way.
  const todayTint = (today) => (today ? { backgroundColor: 'var(--c-a3)' } : undefined)

  // While a swap is armed, an empty slot cannot receive the meal — dim it so
  // the eligible targets are obvious rather than discovered by trial.
  const isDimmed = (meal) => Boolean(armedCell && !meal)

  const selectCell = (iso, idx) =>
    armedCell
      ? onArmSwap({ date: iso, mealIndex: idx })
      : onSelectCell({ date: iso, mealIndex: idx })

  const renderMealCard = (day, idx, isTourAnchor = false) => {
    const iso = fmt(day.date)
    const meal = mealAt(day.date, idx)
    return (
      <MealCard
        key={`${idx}-${iso}`}
        label={MEAL_LABELS[idx]}
        meal={meal}
        armed={isArmed(iso, idx)}
        dimmed={isDimmed(meal)}
        isTourAnchor={isTourAnchor}
        onSelect={() => selectCell(iso, idx)}
        onAccept={() => onAccept({ date: iso, mealIndex: idx })}
        onReject={() => onReject({ date: iso, mealIndex: idx })}
        onArmSwap={() => onArmSwap({ date: iso, mealIndex: idx })}
      />
    )
  }

  // --- Desktop grid cell ----------------------------------------------------
  const renderCell = (d, idx, isTourAnchor = false) => {
    const iso = fmt(d)
    const meal = plan[iso]?.[idx]
    const armed = isArmed(iso, idx)
    const acceptedStyle = meal?.accepted
      ? {
          backgroundColor: 'rgba(12, 58, 45, 0.15)',
          color: 'var(--text-strong)',
        }
      : {}
    // An armed cell (yellow) wins over the accepted/today tints, and adds an
    // outline so the state is not carried by colour alone.
    const armedStyle = armed
      ? {
          backgroundColor: 'rgba(255, 185, 2, 0.25)',
          color: 'var(--text-strong)',
          outline: '2px solid var(--c-a2)',
          outlineOffset: '-2px',
        }
      : {}

    const iconAction = (key, Icon, label, color, handler) => (
      <button
        key={key}
        type="button"
        aria-label={`${label} ${meal.recipe}`}
        title={`${label} ${meal.recipe}`}
        className="inline-flex h-11 w-11 items-center justify-center"
        onClick={(e) => {
          e.stopPropagation()
          handler({ date: iso, mealIndex: idx })
        }}
        style={{ color }}
      >
        <Icon className="h-4 w-4" />
      </button>
    )

    return (
      <div
        key={`${idx}-${iso}`}
        data-cell
        data-tour={isTourAnchor ? 'mealplan-cell' : undefined}
        role="button"
        tabIndex={0}
        className="relative flex min-h-24 flex-col border p-2 cursor-pointer"
        onClick={() => selectCell(iso, idx)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            selectCell(iso, idx)
          }
        }}
        style={{
          borderColor: 'var(--border)',
          opacity: isDimmed(meal) ? 0.45 : 1,
          ...(isToday(d)
            ? {
                color: 'var(--text-strong)',
                ...(meal?.accepted
                  ? acceptedStyle
                  : { backgroundColor: 'rgba(187, 138, 82, 0.15)' }),
              }
            : acceptedStyle),
          ...armedStyle,
        }}
      >
        {meal ? (
          <>
            {/* Fixed-height cells used to spill long titles; clamp instead. */}
            <div className="line-clamp-2 text-sm font-medium">
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
              <div className="mt-1 line-clamp-2 text-xs">
                {meal.side_recipes.join(', ')}
              </div>
            )}
            <div className="mt-1">
              <MealStatusChip accepted={meal.accepted} leftover={meal.leftover} />
            </div>
            <div className="mt-auto flex justify-end">
              {iconAction('swap', ArrowsRightLeftIcon, 'Swap meal', 'var(--c-a2)', onArmSwap)}
              {!meal.accepted && (
                <>
                  {iconAction('reject', XMarkIcon, 'Reject', 'var(--c-neg)', onReject)}
                  {iconAction('accept', CheckIcon, 'Accept', 'var(--c-pos)', onAccept)}
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

  const viewToggle = (
    <div
      className="flex gap-1 p-1"
      role="tablist"
      aria-label="Calendar view"
      style={{ border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}
    >
      {[
        ['day', 'Day'],
        ['week', 'Week'],
      ].map(([value, label]) => (
        <button
          key={value}
          type="button"
          role="tab"
          aria-selected={view === value}
          onClick={() => changeView(value)}
          className="min-h-11 flex-1 text-sm font-medium"
          style={{
            backgroundColor: view === value ? 'var(--c-pos)' : 'transparent',
            color: view === value ? '#fff' : 'var(--text-strong)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )

  return (
    <>
      <CalendarWeekHeader
        weekDays={weekDays}
        onChangeWeek={onChangeWeek}
        onToday={onToday}
        containsToday={Boolean(todayDay)}
      />
      <Card data-tour="mealplan-calendar">
        {armedCell && (
          <SwapBanner recipe={armedMeal?.recipe} onCancel={onCancelSwap} />
        )}
        {isMobile ? (
          <div className="flex flex-col gap-3">
            {viewToggle}
            {view === 'day' ? (
              <>
                <CalendarDayStrip
                  days={days}
                  selectedKey={activeKey}
                  onSelect={setSelectedKey}
                  mealsFor={mealsFor}
                />
                {activeDay && (
                  <div data-testid="mealplan-day" className="flex flex-col gap-2">
                    <div
                      className="px-2 py-1 rounded-lg font-medium"
                      style={{
                        ...todayTint(activeDay.today),
                        color: activeDay.today ? '#fff' : 'var(--text-strong)',
                      }}
                    >
                      {activeDay.long} {activeDay.dm}
                      {activeDay.today && ' · today'}
                    </div>
                    {MEAL_LABELS.map((label, idx) =>
                      renderMealCard(activeDay, idx, idx === 0),
                    )}
                  </div>
                )}
              </>
            ) : (
              days.map((day, i) => (
                <div key={day.key} data-testid="mealplan-day" className="flex flex-col gap-2">
                  <div
                    className={`sticky top-0 z-[1] px-2 py-1 rounded-t-lg font-medium ${day.today ? 'text-white' : ''}`}
                    style={{
                      ...todayTint(day.today),
                      backgroundColor: day.today ? 'var(--c-a3)' : 'var(--page-bg)',
                    }}
                  >
                    {day.long} {day.dm}
                  </div>
                  {MEAL_LABELS.map((label, idx) =>
                    renderMealCard(day, idx, i === 0 && idx === 0),
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          // The grid owns its overflow so the page never scrolls sideways
          // (design guide §8.5); without this, 768-1024px squeezed the columns.
          <div className="overflow-x-auto">
            <div className="grid grid-cols-8 min-w-[46rem]">
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
          </div>
        )}
      </Card>
    </>
  )
}
