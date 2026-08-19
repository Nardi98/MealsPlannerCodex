/* global process */
const API_BASE_URL =
  (typeof import.meta !== 'undefined' &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  (typeof process !== 'undefined' &&
    (process.env.REACT_APP_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL)) ||
  '';

// The access token lives in memory only — never localStorage — so it cannot be
// read by injected scripts. Durable session state is the HttpOnly refresh cookie
// the server sets; we recover the access token from it via /auth/refresh.
let accessToken = null;

// Called when the session is irrecoverable (refresh failed) so the app can drop
// the session and route back to login. Registered by the auth layer at startup.
let unauthorizedHandler = null;

// De-dupes concurrent refreshes: many in-flight requests hitting 401 at once
// should share a single /auth/refresh round-trip.
let refreshPromise = null;

function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function getToken() {
  return accessToken;
}

function setAuthToken(token) {
  accessToken = token || null;
}

function buildConfig(options) {
  // Let the browser set the multipart boundary itself for FormData uploads;
  // forcing application/json here would break the request.
  const isFormData =
    typeof FormData !== 'undefined' && options.body instanceof FormData;
  const defaultHeaders = isFormData ? {} : { 'Content-Type': 'application/json' };
  if (accessToken) defaultHeaders['Authorization'] = `Bearer ${accessToken}`;
  return {
    ...options,
    // Send the refresh cookie (and receive Set-Cookie) on every call.
    credentials: 'include',
    headers: { ...defaultHeaders, ...(options.headers || {}) },
  };
}

// Exchanges the HttpOnly refresh cookie for a fresh access token. Returns the
// new token on success, or null when the cookie is missing/revoked/expired.
// Deliberately a raw fetch (not request()) so a 401 here cannot recurse.
async function attemptRefresh() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(async (res) => {
        if (!res.ok) return null;
        const data = await res.json().catch(() => null);
        return data && data.access_token ? data.access_token : null;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  const token = await refreshPromise;
  if (token) setAuthToken(token);
  return token;
}

async function request(path, options = {}, allowRefresh = true) {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, buildConfig(options));

  if (!response.ok) {
    if (response.status === 401) {
      // Try to silently refresh the access token exactly once, then replay the
      // original request. /auth/refresh itself is exempt to avoid recursion.
      if (allowRefresh && path !== '/auth/refresh') {
        const newToken = await attemptRefresh();
        if (newToken) return request(path, options, false);
      }
      // No recovery — the session is dead. Drop it and notify the app.
      setAuthToken(null);
      if (unauthorizedHandler) unauthorizedHandler();
    }
    const text = await response.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    const message =
      (data && typeof data.detail === 'string')
        ? data.detail
        : text || `Request failed with status ${response.status}`;
    const error = new Error(message);
    // Callers that must react to a specific status (e.g. wording a 429 rate
    // limit calmly rather than as a generic failure) need it off the error.
    error.status = response.status;
    if (data) error.data = data;
    throw error;
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export { request, getToken, setAuthToken, setUnauthorizedHandler };
