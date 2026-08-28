import MealStatusChip from './MealStatusChip'
import {
  CheckIcon,
  XMarkIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'

/**
 * One meal slot as a full-width card, used by both mobile layouts.
 *
 * Replaces the old grid square, whose three 16px icons sat 4px apart in a
 * corner — with reject next to accept and no undo. Here the actions are a
 * labelled 44px row (design guide §8.4), and the card itself stays tappable to
 * open the detail modal for sides and search-swap.
 */
export default function MealCard({
  label,
  meal,
  armed,
  dimmed,
  isTourAnchor,
  onSelect,
  onAccept,
  onReject,
  onArmSwap,
}) {
  const activate = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect()
    }
  }

  const action = (key, Icon, text, color, handler) => (
    <button
      key={key}
      type="button"
      aria-label={`${text} ${meal.recipe}`}
      onClick={(e) => {
        e.stopPropagation()
        handler()
      }}
      className="inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 text-sm"
      style={{
        color,
        border: '1px solid var(--border-default)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <Icon className="h-5 w-5" />
      {text}
    </button>
  )

  if (!meal) {
    return (
      <div
        data-cell
        data-testid="meal-card"
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={activate}
        className="flex min-h-11 items-center gap-2 p-3 text-sm"
        style={{
          border: '1px dashed var(--border-default)',
          borderRadius: 'var(--radius-lg)',
          color: 'var(--text-subtle)',
        }}
      >
        <span className="font-medium">{label}</span>
        <span>— nothing planned</span>
      </div>
    )
  }

  return (
    <div
      data-cell
      data-testid="meal-card"
      data-tour={isTourAnchor ? 'mealplan-cell' : undefined}
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={activate}
      className="flex flex-col gap-2 p-3"
      style={{
        backgroundColor: armed
          ? 'rgba(255, 185, 2, 0.25)'
          : meal.accepted
            ? 'rgba(12, 58, 45, 0.15)'
            : 'var(--surface, #fff)',
        // The armed state gets a shape cue, not only a tint, so it reads
        // against the today/accepted tints it used to be confused with.
        border: armed ? '2px solid var(--c-a2)' : '1px solid var(--border-default)',
        borderRadius: 'var(--radius-lg)',
        color: 'var(--text-strong)',
        opacity: dimmed ? 0.45 : 1,
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--text-subtle)' }}>
          {label}
        </span>
        <MealStatusChip accepted={meal.accepted} />
      </div>

      <div className="min-w-0 font-medium">
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
        <div className="text-xs" style={{ color: 'var(--text-subtle)' }}>
          + {meal.side_recipes.join(', ')}
        </div>
      )}

      <div className="flex gap-2">
        {!meal.accepted &&
          action('accept', CheckIcon, 'Accept', 'var(--c-pos)', onAccept)}
        {action('swap', ArrowsRightLeftIcon, 'Swap meal', 'var(--c-a2)', onArmSwap)}
        {!meal.accepted &&
          action('reject', XMarkIcon, 'Reject', 'var(--c-neg)', onReject)}
      </div>
    </div>
  )
}
