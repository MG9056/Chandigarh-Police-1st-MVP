// Centralized fetch wrapper for authenticated API calls.
//
// Why this exists: access tokens expire after 15 minutes (see
// backend/security.py). Without this, every view that calls fetch()
// directly starts silently failing 15 minutes after login, because
// nothing ever calls POST /api/auth/refresh.
//
// Usage: swap fetch('/api/...') for apiFetch('/api/...') anywhere the
// request needs an authenticated session.

let onAuthFailure = null;

// Called once by AuthProvider on mount so this module can trigger a
// logout / redirect-to-login when a session can't be recovered.
export function registerAuthFailureHandler(handler) {
  onAuthFailure = handler;
}

// Prevents concurrent 401s (e.g. two widgets loading at once) from firing
// multiple simultaneous refresh requests.
let refreshPromise = null;

async function attemptRefresh() {
  if (!refreshPromise) {
    refreshPromise = fetch('/api/auth/refresh', { method: 'POST' })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function apiFetch(input, init = {}) {
  let response = await fetch(input, init);

  if (response.status === 401) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      response = await fetch(input, init); // retry once with the new access token
    }
    if (response.status === 401 && onAuthFailure) {
      onAuthFailure(); // refresh token is also dead — log the user out properly
    }
  }

  return response;
}