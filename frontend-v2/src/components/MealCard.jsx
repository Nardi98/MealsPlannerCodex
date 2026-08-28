import MealStatusChip from './MealStatusChip'
import LeftoverIcon from './LeftoverIcon'
import { actionsFor, onActivateKey } from '../lib/mealActions'

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
  ...actions
}) {
  if (!meal) {
    return (
      <div
        data-cell
        data-testid="meal-card"
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={onActivateKey(onSelect)}
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
      onKeyDown={onActivateKey(onSelect)}
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
        {meal.leftover && <LeftoverIcon />}
      </div>

      {meal.side_recipes && meal.side_recipes.length > 0 && (
        <div className="text-xs" style={{ color: 'var(--text-subtle)' }}>
          + {meal.side_recipes.join(', ')}
        </div>
      )}

      <div className="flex gap-2">
        {actionsFor(meal).map((a) => (
          <button
            key={a.key}
            type="button"
            aria-label={`${a.label} ${meal.recipe}`}
            onClick={(e) => {
              e.stopPropagation()
              actions[a.handler]()
            }}
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 text-sm"
            style={{
              color: a.color,
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <a.Icon className="h-5 w-5" />
            {a.label}
          </button>
        ))}
      </div>
    </div>
  )
}
