import { Button } from './Button'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import { formatWeekRange } from '../lib/weekRange'

/**
 * Week navigation with the one thing the calendar never had: a statement of
 * which week you are looking at, plus a way back to today. Previously the only
 * date context was a `D/M` in each column header, so on a phone — where the
 * columns are gone — you could scroll a plan with no idea where you were.
 */
export default function CalendarWeekHeader({ weekDays, onChangeWeek, onToday, containsToday }) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2"
      data-tour="mealplan-week-nav"
    >
      <Button
        variant="ghost"
        aria-label="Previous week"
        onClick={() => onChangeWeek(-1)}
      >
        <ChevronLeftIcon className="h-5 w-5" />
      </Button>
      <div className="flex min-w-0 flex-col items-center">
        <span className="font-medium" style={{ color: 'var(--text-strong)' }}>
          {formatWeekRange(weekDays)}
        </span>
        {!containsToday && (
          <button
            type="button"
            onClick={onToday}
            className="text-xs underline"
            style={{ color: 'var(--c-a1)' }}
          >
            Back to today
          </button>
        )}
      </div>
      <Button
        variant="ghost"
        aria-label="Next week"
        onClick={() => onChangeWeek(1)}
      >
        <ChevronRightIcon className="h-5 w-5" />
      </Button>
    </div>
  )
}
