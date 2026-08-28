import { Badge } from './Badge'

/**
 * The accept/pending state of a meal, as a labelled chip.
 *
 * The calendar used to carry this meaning in the cell's background tint alone,
 * which is invisible to anyone who cannot separate the three overlapping tints
 * (today / accepted / armed) and unreadable on a phone in daylight. The chip is
 * the non-colour cue; the tints stay as reinforcement.
 */
export default function MealStatusChip({ accepted, leftover }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <Badge tone={accepted ? 'pos' : 'caramel'}>
        {accepted ? 'Accepted' : 'Pending'}
      </Badge>
      {leftover && <Badge tone="sage">Leftover</Badge>}
    </span>
  )
}
