// The only place that knows how "this user has seen a tour" is persisted.
//
// Deliberately localStorage and not the account: the flag is a per-browser
// convenience, not user data worth a migration and an endpoint. A user on a new
// device seeing the tutorial again is the acceptable cost.
//
// Every access is guarded. Reading `window.localStorage` itself throws in
// browsers configured to block site data — not just the get/set calls — and a
// tutorial must never be able to break the page it is teaching.

import { TOURS } from './steps'

// Derived, never hand-maintained: a tour added to the registry is one
// "Skip tutorial" can silence, with no second list to remember to update.
export const TOUR_IDS = Object.keys(TOURS)

const KEY_PREFIX = 'tutorial:'

function keyFor(id) {
  return `${KEY_PREFIX}${id}`
}

function store() {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function isTourDone(id) {
  try {
    return store()?.getItem(keyFor(id)) === 'done'
  } catch {
    return false
  }
}

export function markTourDone(id) {
  try {
    store()?.setItem(keyFor(id), 'done')
  } catch {
    /* storage unavailable — the tour simply runs again next time */
  }
}

// "Skip tutorial" means the user said no to the tutorial, not to this page's
// tour, so it silences all of them. The header replay button is the way back.
export function markAllToursDone() {
  for (const id of TOUR_IDS) markTourDone(id)
}

