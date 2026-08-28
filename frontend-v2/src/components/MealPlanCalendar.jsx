import React from 'react'
import { Card } from './Card'
import { IconButton } from './IconButton'
import { useIsMobile } from '../hooks/useIsMobile'
import { usePersistedState } from '../hooks/usePersistedState'
import MealCard from './MealCard'
import LeftoverIcon from './LeftoverIcon'
import { actionsFor, onActivateKey } from '../lib/mealActions'
import MealStatusChip from './MealStatusChip'
import SwapBanner from './SwapBanner'
import CalendarWeekHeader from './CalendarWeekHeader'
import CalendarDayStrip from './CalendarDayStrip'
import CalendarViewToggle from './CalendarViewToggle'

// Index 0/1 here are the backend's `meal_number` 1/2.
const MEAL_LABELS = ['Lunch', 'Dinner']

// Which mobile layout was last used. Someone who plans in Week view should not
// be dropped back into Day view on every visit.
const VIEW_KEY = 'mp.calendarView'
const VIEWS = [
  ['day', 'Day'],
  ['week', 'Week'],
]

// The accepted / armed / today cell tints. Each is a token colour at low
// alpha; they live here so the grid and the meal card cannot drift apart.
const ACCEPTED_TINT = 'rgba(12, 58, 45, 0.15)'
const ARMED_TINT = 'rgba(255, 185, 2, 0.25)'
const TODAY_TINT = 'rgba(187, 138, 82, 0.15)'

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
  const [view, setView] = usePersistedState(VIEW_KEY, 'day', (v) => v === 'week')

  // Each entry carries everything both layouts need, including its meals, so
  // the strip and the cards never re-run the per-day lookup or reformat dates.
  const days = React.useMemo(
    () =>
      weekDays.map((d) => {
        const iso = fmt(d)
        const meals = plan[iso] || []
        return {
          date: d,
          iso,
          key: d.toISOString(),
          short: d.toLocaleDateString(undefined, { weekday: 'short' }),
          long: d.toLocaleDateString(undefined, { weekday: 'long' }),
          dm: `${d.getDate()}/${d.getMonth() + 1}`,
          today: isToday(d),
          meals: MEAL_LABELS.map((_, idx) => meals[idx]).filter(Boolean),
          mealAt: (idx) => meals[idx],
        }
      }),
    [weekDays, plan, fmt, isToday],
  )

  const todayDay = days.find((d) => d.today)
  const [selectedKey, setSelectedKey] = React.useState(null)
  // Follow the viewed week: land on today when it is in range, else day one.
  const activeDay = days.find((d) => d.key === selectedKey) ?? todayDay ?? days[0]

  const isArmed = (iso, idx) =>
    Boolean(armedCell && armedCell.date === iso && armedCell.mealIndex === idx)

  const armedMeal = armedCell
    ? plan[armedCell.date]?.[armedCell.mealIndex]
    : null

  // While a swap is armed, an empty slot cannot receive the meal — dim it so
  // the eligible targets are obvious rather than discovered by trial.
  const isDimmed = (meal) => Boolean(armedCell && !meal)

  const selectCell = (ref) => (armedCell ? onArmSwap(ref) : onSelectCell(ref))

  const handlers = (ref) => ({
    onSelect: () => selectCell(ref),
    onAccept: () => onAccept(ref),
    onReject: () => onReject(ref),
    onArmSwap: () => onArmSwap(ref),
  })

  const dayHeader = (day, { sticky }) => (
    <div
      className={`px-2 py-1 font-medium ${sticky ? 'sticky top-0 z-[1] rounded-t-lg' : 'rounded-lg'}`}
      style={{
        backgroundColor: day.today
          ? 'var(--c-a3)'
          : sticky
            ? 'var(--page-bg)'
            : undefined,
        color: day.today ? '#fff' : 'var(--text-strong)',
      }}
    >
      {day.long} {day.dm}
      {day.today && ' · today'}
    </div>
  )

  const renderMealCard = (day, idx, isTourAnchor = false) => {
    const meal = day.mealAt(idx)
    return (
      <MealCard
        key={`${idx}-${day.iso}`}
        label={MEAL_LABELS[idx]}
        meal={meal}
        armed={isArmed(day.iso, idx)}
        dimmed={isDimmed(meal)}
        isTourAnchor={isTourAnchor}
        {...handlers({ date: day.iso, mealIndex: idx })}
      />
    )
  }

  // --- Desktop grid cell ----------------------------------------------------
  const renderCell = (day, idx, isTourAnchor = false) => {
    const meal = day.mealAt(idx)
    const armed = isArmed(day.iso, idx)
    const act = handlers({ date: day.iso, mealIndex: idx })

    const acceptedStyle = meal?.accepted
      ? { backgroundColor: ACCEPTED_TINT, color: 'var(--text-strong)' }
      : {}
    // An armed cell (yellow) wins over the accepted/today tints, and adds an
    // outline so the state is not carried by colour alone.
    const armedStyle = armed
      ? {
          backgroundColor: ARMED_TINT,
          color: 'var(--text-strong)',
          outline: '2px solid var(--c-a2)',
          outlineOffset: '-2px',
        }
      : {}

    return (
      <div
        key={`${idx}-${day.iso}`}
        data-cell
        data-tour={isTourAnchor ? 'mealplan-cell' : undefined}
        role="button"
        tabIndex={0}
        className="relative flex min-h-24 flex-col border p-2 cursor-pointer"
        onClick={act.onSelect}
        onKeyDown={onActivateKey(act.onSelect)}
        style={{
          borderColor: 'var(--border)',
          opacity: isDimmed(meal) ? 0.45 : 1,
          ...(day.today
            ? {
                color: 'var(--text-strong)',
                ...(meal?.accepted ? acceptedStyle : { backgroundColor: TODAY_TINT }),
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
              {meal.leftover && <LeftoverIcon />}
            </div>
            {meal.side_recipes && meal.side_recipes.length > 0 && (
              <div className="mt-1 line-clamp-2 text-xs">
                {meal.side_recipes.join(', ')}
              </div>
            )}
            <div className="mt-1">
              <MealStatusChip accepted={meal.accepted} />
            </div>
            <div className="mt-auto flex justify-end">
              {actionsFor(meal).map((a) => (
                <IconButton
                  key={a.key}
                  Icon={a.Icon}
                  label={`${a.label} ${meal.recipe}`}
                  color={a.color}
                  stopPropagation
                  onClick={act[a.handler]}
                />
              ))}
            </div>
          </>
        ) : (
          <div className="text-sm text-[color:var(--text-subtle)]">—</div>
        )}
      </div>
    )
  }

  // Day view shows one day, week view all seven; the day block is identical.
  const shownDays = view === 'day' ? (activeDay ? [activeDay] : []) : days

  return (
    <>
      <CalendarWeekHeader
        weekDays={weekDays}
        onChangeWeek={onChangeWeek}
        onToday={onToday}
      />
      <Card data-tour="mealplan-calendar">
        {armedCell && (
          <SwapBanner recipe={armedMeal?.recipe} onCancel={onCancelSwap} />
        )}
        {isMobile ? (
          <div className="flex flex-col gap-3">
            <CalendarViewToggle value={view} onChange={setView} options={VIEWS} />
            {view === 'day' && (
              <CalendarDayStrip
                days={days}
                selectedKey={activeDay?.key}
                onSelect={setSelectedKey}
              />
            )}
            {shownDays.map((day, i) => (
              <div key={day.key} data-testid="mealplan-day" className="flex flex-col gap-2">
                {dayHeader(day, { sticky: view === 'week' })}
                {MEAL_LABELS.map((_, idx) =>
                  renderMealCard(day, idx, i === 0 && idx === 0),
                )}
              </div>
            ))}
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
                  style={{ backgroundColor: day.today ? 'var(--c-a3)' : undefined }}
                >
                  <div className="font-medium">{day.short}</div>
                  <div className="text-sm">{day.dm}</div>
                </div>
              ))}
              {MEAL_LABELS.map((label, idx) => (
                <React.Fragment key={label}>
                  <div className="p-2 text-left font-medium">{label}</div>
                  {days.map((day, i) => renderCell(day, idx, idx === 0 && i === 0))}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
      </Card>
    </>
  )
}
