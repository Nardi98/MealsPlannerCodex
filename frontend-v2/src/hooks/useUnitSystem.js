import { useOptionalAuth } from '../auth/AuthContext'

/**
 * Which system this account reads amounts in: `metric` or `us`.
 *
 * Display only. It rides on the account rather than on the device so it
 * follows the user, and it is applied at render time by `formatAmount`, which
 * is why toggling it is instant and cannot touch a stored quantity.
 *
 * Metric until an account says otherwise, which covers a session that has not
 * loaded its user yet, one that never set the preference, and a component
 * rendered on its own with no provider around it.
 */
export function useUnitSystem() {
  return useOptionalAuth()?.user?.unit_system === 'us' ? 'us' : 'metric'
}
