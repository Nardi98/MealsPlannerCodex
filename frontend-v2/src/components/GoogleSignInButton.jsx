import React from 'react'
import { loadGoogleIdentityServices } from '../auth/googleSignIn'

/**
 * Google's own sign-in button, rendered by Google Identity Services.
 *
 * Calls `onCredential` with the ID token Google returns; the caller exchanges
 * it for one of our JWTs. Renders a hint instead when the deployment has no
 * `VITE_GOOGLE_CLIENT_ID` configured.
 */
export default function GoogleSignInButton({ onCredential }) {
  const clientId = import.meta.env?.VITE_GOOGLE_CLIENT_ID || ''
  const containerRef = React.useRef(null)
  const [error, setError] = React.useState('')

  // Keep the latest callback reachable without re-initializing GIS on every
  // render of the parent.
  const onCredentialRef = React.useRef(onCredential)
  React.useEffect(() => {
    onCredentialRef.current = onCredential
  }, [onCredential])

  React.useEffect(() => {
    if (!clientId) return
    let active = true
    loadGoogleIdentityServices()
      .then((id) => {
        if (!active) return
        id.initialize({
          client_id: clientId,
          callback: (response) => onCredentialRef.current(response.credential),
        })
        id.renderButton(containerRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          width: 340,
        })
      })
      .catch((err) => active && setError(err.message))
    return () => {
      active = false
    }
  }, [clientId])

  if (!clientId) {
    return (
      <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
        Google sign-in is not configured.
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div ref={containerRef} />
      {error && (
        <div role="alert" style={{ fontSize: 12, color: 'var(--c-neg)' }}>
          {error}
        </div>
      )}
    </div>
  )
}
