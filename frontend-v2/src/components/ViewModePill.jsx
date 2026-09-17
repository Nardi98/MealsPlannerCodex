import { UserIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import { useNavigate } from 'react-router-dom'
import ViewToggle from './ViewToggle'
import { useViewMode } from '../auth/ViewModeContext'

// `sr-only md:not-sr-only` rather than `hidden md:inline`: the word is the
// button's accessible name at every width, so the icon-only phone layout is
// still announced as "User" / "Admin" instead of as an unlabelled button.
const segment = (Icon, word) => (
  <span className="flex items-center justify-center gap-1.5">
    <Icon className="h-5 w-5" aria-hidden="true" />
    <span className="sr-only md:not-sr-only">{word}</span>
  </span>
)

const OPTIONS = [
  ['user', segment(UserIcon, 'User')],
  ['admin', segment(ShieldCheckIcon, 'Admin')],
]

/**
 * The header's User/Admin switch, rendered only for an admin account.
 *
 * Switching is a change of destination as much as a change of chrome: admin
 * mode has exactly one surface, so it opens the library, and coming back opens
 * the recipe book rather than leaving the user on a page the admin sidebar no
 * longer lists. The navigation lives here and not in `ViewModeContext` so the
 * mode itself stays a plain piece of state with no opinion about routing.
 */
export default function ViewModePill() {
  const { mode, canAdmin, setMode } = useViewMode()
  const navigate = useNavigate()

  if (!canAdmin) return null

  return (
    <ViewToggle
      value={mode}
      options={OPTIONS}
      onChange={(next) => {
        setMode(next)
        navigate(next === 'admin' ? '/discover' : '/recipes')
      }}
    />
  )
}
