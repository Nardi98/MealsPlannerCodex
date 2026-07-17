const GIS_SRC = 'https://accounts.google.com/gsi/client'

let loader = null

/**
 * Load Google Identity Services once and resolve with `google.accounts.id`.
 * The script is injected on demand so the login page is the only thing that
 * ever pays for it.
 */
export function loadGoogleIdentityServices() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id)
  if (loader) return loader

  loader = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.onload = () => {
      if (window.google?.accounts?.id) resolve(window.google.accounts.id)
      else reject(new Error('Google Identity Services loaded without an id client'))
    }
    script.onerror = () => {
      loader = null
      reject(new Error('Could not load Google Identity Services'))
    }
    document.head.appendChild(script)
  })
  return loader
}
