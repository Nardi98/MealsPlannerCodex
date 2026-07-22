import React from 'react'
// Aliased to a capitalized name so the lint config (no eslint-plugin-react)
// recognizes the JSX usage below.
import { AnimatePresence, motion as Motion } from 'framer-motion'
import { ArrowRightOnRectangleIcon, Cog6ToothIcon } from '@heroicons/react/24/outline'
import Avatar from './Avatar'
import PreferencesModal from './PreferencesModal'
import { useAuth } from '../auth/AuthContext'

export default function ProfileMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = React.useState(false)
  const [showPreferences, setShowPreferences] = React.useState(false)
  const ref = React.useRef(null)

  // Close the dropdown when clicking anywhere outside it.
  React.useEffect(() => {
    if (!open) return
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  if (!user) return null

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
        style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', lineHeight: 0 }}
      >
        <Avatar name={user.display_name} email={user.email} />
      </button>

      <AnimatePresence>
        {open && (
          <Motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.14 }}
            style={{
              position: 'absolute',
              right: 0,
              top: 'calc(100% + 8px)',
              minWidth: 220,
              background: 'var(--surface-card)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-lg)',
              border: '1px solid var(--border-default)',
              padding: 8,
              zIndex: 50,
            }}
          >
            <div style={{ padding: '8px 10px' }}>
              {user.display_name && (
                <div
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontWeight: 'var(--weight-medium)',
                    fontSize: 14,
                    color: 'var(--text-strong)',
                  }}
                >
                  {user.display_name}
                </div>
              )}
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{user.email}</div>
            </div>
            <div style={{ height: 1, background: 'var(--border-default)', margin: '6px 0' }} />
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                setShowPreferences(true)
              }}
              className="flex items-center gap-2"
              style={menuItemStyle}
            >
              <Cog6ToothIcon className="h-5 w-5" />
              Preferences
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                logout()
              }}
              className="flex items-center gap-2"
              style={menuItemStyle}
            >
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
              Log out
            </button>
          </Motion.div>
        )}
      </AnimatePresence>
      {showPreferences && (
        <PreferencesModal onClose={() => setShowPreferences(false)} />
      )}
    </div>
  )
}

const menuItemStyle = {
  width: '100%',
  padding: '8px 10px',
  background: 'none',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  color: 'var(--text-strong)',
  fontSize: 14,
  fontFamily: 'var(--font-body)',
}
