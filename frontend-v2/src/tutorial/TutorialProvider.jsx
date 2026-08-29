import React from 'react'
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline'
import { IconButton } from '../components/IconButton'
import { TutorialContext, useTutorial } from './tutorialContext'

// Lets the header's help button replay whichever page's tour is on screen,
// without the header having to know which page that is.
//
// The mounted `<PageTour>` registers its `start`; the button calls it. Pages
// with no tour register nothing, and the button hides itself — better than a
// help control that does nothing when pressed.

export function TutorialProvider({ children }) {
  const starter = React.useRef(null)
  const [hasTour, setHasTour] = React.useState(false)

  // The ref, not state, holds the callback: it keeps `register` and `replay`
  // stable, so the only thing that pushes a new context value through the whole
  // shell is a real "a tour appeared / went away" transition.
  const register = React.useCallback((start) => {
    starter.current = start
    // React bails out when the value is unchanged, so a re-registering page
    // costs nothing.
    setHasTour(true)
    return () => {
      // Only the tour that registered may deregister: on a route change the new
      // page can mount before the old one unmounts, and the loser's cleanup
      // must not wipe the winner's registration.
      if (starter.current === start) {
        starter.current = null
        setHasTour(false)
      }
    }
  }, [])

  const replay = React.useCallback(() => {
    starter.current?.()
  }, [])

  const value = React.useMemo(() => ({ register, replay, hasTour }), [register, replay, hasTour])
  return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>
}

export function ReplayTutorialButton() {
  const { hasTour, replay } = useTutorial()
  if (!hasTour) return null
  return (
    <IconButton
      Icon={QuestionMarkCircleIcon}
      label="Replay tutorial"
      onClick={replay}
      color="var(--text-muted)"
    />
  )
}
