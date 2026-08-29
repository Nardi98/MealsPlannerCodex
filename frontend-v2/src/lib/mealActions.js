import {
  CheckIcon,
  XMarkIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'

/**
 * The three per-meal actions, in the order they are offered, described once.
 *
 * Both calendar layouts render these — the grid as icon-only buttons, the card
 * as a labelled row — and both hide accept/reject on an accepted meal. Keeping
 * the icon, tone and that rule in one list is what stops the two drifting.
 */
export const MEAL_ACTIONS = [
  { key: 'accept', Icon: CheckIcon, label: 'Accept', color: 'var(--c-pos)', handler: 'onAccept' },
  { key: 'swap', Icon: ArrowsRightLeftIcon, label: 'Swap meal', color: 'var(--c-a2)', handler: 'onArmSwap', always: true },
  { key: 'reject', Icon: XMarkIcon, label: 'Reject', color: 'var(--c-neg)', handler: 'onReject' },
]

/** The actions offered for a given meal: accepted meals only offer the swap. */
export const actionsFor = (meal) =>
  MEAL_ACTIONS.filter((a) => a.always || !meal.accepted)

/** Enter/Space on an element given `role="button"`, which does not get it free. */
export const onActivateKey = (handler) => (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    handler()
  }
}
