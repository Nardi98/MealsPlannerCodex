/* global process */
const API_BASE_URL =
  (typeof import.meta !== 'undefined' &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  (typeof process !== 'undefined' &&
    (process.env.REACT_APP_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL)) ||
  '';

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const defaultHeaders = { 'Content-Type': 'application/json' };
  const config = { ...options, headers: { ...defaultHeaders, ...(options.headers || {}) } };

  const response = await fetch(url, config);
  if (!response.ok) {
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

export { request };
