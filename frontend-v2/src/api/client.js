/* global process */
const API_BASE_URL =
  (typeof import.meta !== 'undefined' &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  (typeof process !== 'undefined' &&
    (process.env.REACT_APP_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL)) ||
  '';

const TOKEN_KEY = 'auth_token';

// Called when the backend rejects our credentials (401) so the app can drop the
// session and route back to login. Registered by the auth layer at startup.
let unauthorizedHandler = null;

function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function getToken() {
  try {
    return (typeof localStorage !== 'undefined' && localStorage.getItem(TOKEN_KEY)) || null;
  } catch {
    return null;
  }
}

function setAuthToken(token) {
  try {
    if (typeof localStorage === 'undefined') return;
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable (e.g. private mode) — token simply won't persist.
  }
}

function getApiKey() {
  return (
    (typeof import.meta !== 'undefined' &&
      import.meta.env &&
      import.meta.env.VITE_API_KEY) ||
    ''
  );
}

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  // Let the browser set the multipart boundary itself for FormData uploads;
  // forcing application/json here would break the request.
  const isFormData =
    typeof FormData !== 'undefined' && options.body instanceof FormData;
  const defaultHeaders = isFormData ? {} : { 'Content-Type': 'application/json' };
  const apiKey = getApiKey();
  if (apiKey) defaultHeaders['X-API-Key'] = apiKey;
  const token = getToken();
  if (token) defaultHeaders['Authorization'] = `Bearer ${token}`;
  const config = { ...options, headers: { ...defaultHeaders, ...(options.headers || {}) } };

  const response = await fetch(url, config);
  if (!response.ok) {
    if (response.status === 401) {
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
    if (data) error.data = data;
    throw error;
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export { request, getToken, setAuthToken, setUnauthorizedHandler };
