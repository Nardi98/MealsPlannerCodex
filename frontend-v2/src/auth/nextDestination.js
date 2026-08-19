// SH-23: where to send a visitor after they sign in.
//
// The problem. Someone is sent a person-mode share link, opens it signed out,
// and the server-rendered page redirects them to `/login?next=/s/<token>`.
// Without this module the SPA drops the `next` entirely: they sign in, land on
// the recipe list, and the only way back to what they were sent is to go and
// find the original message again. The token is the whole point of the visit,
// and it was thrown away at the door.
//
// The danger. `next` is a query parameter, so it is written by whoever composed
// the URL — an attacker, in the case worth defending against. Redirecting to it
// unchecked is a textbook **open redirect**: `/login?next=https://evil.example`
// is a link on this product's own domain that deposits the user on somebody
// else's page *after* they have inspected the domain and decided to trust it.
// That is more valuable to a phisher than any share token, and it is entirely
// our fault if we build it.
//
// The rule. Only a **same-origin absolute path** is ever returned. This is a
// whitelist — a value is accepted because it matched the one shape we allow,
// not because it failed to match a list of known-bad shapes. That distinction
// matters: the attacker chooses the input, so any blacklist is a list of the
// tricks we happened to think of, and the interesting attack is always the one
// that is not on it.

//: A destination we will navigate to: one leading slash, then anything that is
//: not another slash or a backslash. The second character is the whole defence
//: against `//evil.example` and `/\evil.example`, both of which browsers and
//: the URL parser read as protocol-relative — an authority, not a path.
const SAME_ORIGIN_PATH = /^\/(?![/\\])[^\s]*$/

//: Any URL scheme at all (`https:`, `javascript:`, `data:`, `weird-app:`).
//: Checked before the shape test rather than relying on it, so that the
//: rejection of `javascript:alert(1)` is explicit and readable rather than an
//: accident of the leading-slash requirement.
const HAS_SCHEME = /^[a-z][a-z0-9+.-]*:/i

//: The backend's share path. It is rewritten rather than followed — see below.
const SERVER_SHARE_PREFIX = '/s/'
const APP_SHARE_PREFIX = '/shared/'

// Percent-encoding is decoded before the shape check so that `/%2f%2fevil.example`
// cannot smuggle an authority past a test that only looks at literal slashes.
// A malformed escape sequence throws, and a value we cannot even decode is not
// one we are going to navigate to.
function decodedOrNull(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return null
  }
}

/**
 * Return `raw` as a safe same-origin path, or `null` if it is not one.
 *
 * `null` is the only failure signal: there is nothing useful to say about *why*
 * a destination was refused, and the caller's response is the same either way
 * (fall back to the default landing page).
 */
export function safeNextPath(raw) {
  // Strictly a string. An object with a hostile `toString` is not input we
  // coerce; it is input we decline.
  if (typeof raw !== 'string') return null

  // Not trimmed, and control characters are rejected wherever they appear.
  // Whitespace and C0 bytes exist in a value like this for exactly one reason —
  // to hide a scheme or an authority from a check that looks only at the first
  // character — and a legitimate `next` never contains any, so their presence
  // is itself the answer. Tested by code point rather than by regex: a regex
  // literal holding raw control characters is unreadable and unreviewable,
  // which is precisely what eslint's `no-control-regex` is warning about.
  if (raw === '') return null
  for (let i = 0; i < raw.length; i += 1) {
    const code = raw.charCodeAt(i)
    if (code <= 0x20 || code === 0x7f) return null
  }
  if (HAS_SCHEME.test(raw)) return null
  if (!SAME_ORIGIN_PATH.test(raw)) return null

  const decoded = decodedOrNull(raw)
  if (decoded === null) return null
  if (!SAME_ORIGIN_PATH.test(decoded)) return null

  // `/s/<token>` is the *server-rendered* share page, and following it after
  // sign-in would loop for a person-mode share: the access token lives in
  // memory only, so a full-page navigation carries no Authorization header,
  // the server sees an anonymous visitor, and sends them back to
  // `/login?next=/s/<token>` again. The in-app route reads the same token
  // through the authenticated API and terminates.
  if (raw.startsWith(SERVER_SHARE_PREFIX)) {
    return APP_SHARE_PREFIX + raw.slice(SERVER_SHARE_PREFIX.length)
  }
  return raw
}

/**
 * Read and validate the `next` parameter out of a location's query string.
 *
 * `URLSearchParams.get` returns the *first* occurrence, which is the behaviour
 * we want pinned: where a repeated parameter is read differs between proxies
 * and frameworks, and taking the first means a hostile second copy appended to
 * a legitimate link never wins.
 */
export function nextFromSearch(search) {
  if (typeof search !== 'string' || search === '') return null
  return safeNextPath(new URLSearchParams(search).get('next'))
}
