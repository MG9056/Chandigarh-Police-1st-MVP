import API_BASE_URL from '../config/api';

// Centralized fetch wrapper for authenticated API calls.
//
// Access tokens expire after 15 minutes.
// If an authenticated request returns 401, attempt to refresh the
// access token once and retry the original request.

let onAuthFailure = null;

export function registerAuthFailureHandler(handler) {
  onAuthFailure = handler;
}

let refreshPromise = null;

function resolveApiUrl(input) {
  if (
    typeof input === 'string' &&
    (input.startsWith('http://') || input.startsWith('https://'))
  ) {
    return input;
  }

  if (typeof input === 'string' && input.startsWith('/api/')) {
    return `${API_BASE_URL}${input}`;
  }

  if (typeof input === 'string' && input.startsWith('api/')) {
    return `${API_BASE_URL}/${input}`;
  }

  return input;
}

async function attemptRefresh() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
      .then((response) => response.ok)
      .catch((error) => {
        console.error('Token refresh failed:', error);
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

export async function apiFetch(input, init = {}) {
  const url = resolveApiUrl(input);

  const requestInit = {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.headers || {}),
    },
  };

  let response = await fetch(url, requestInit);

  if (response.status === 401) {
    const refreshed = await attemptRefresh();

    if (refreshed) {
      response = await fetch(url, requestInit);
    }

    if (response.status === 401 && onAuthFailure) {
      onAuthFailure();
    }
  }

  return response;
}